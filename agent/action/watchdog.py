"""卡死检测自定义动作。

通过周期性截图对比判断画面是否长时间无变化；检测到卡死（或进程已退出）时返回成功，
由后续 pipeline 节点执行「关闭游戏 → 打开游戏」完成自动重启。
"""

from __future__ import annotations

import hashlib
import json
import time

from maa.custom_action import CustomAction

from loggerControl import LoggerControl

logger = LoggerControl(__name__).logger

_DEFAULT_PACKAGE = "com.fyf.newslggf"
_DEFAULT_FREEZE_SECONDS = 60.0
_DEFAULT_INTERVAL = 2.0
_MIN_FREEZE_SECONDS = 5.0
_MIN_INTERVAL = 0.2
_SCREENCAP_TIMEOUT = 5.0


def _screencap(controller):
    """同步截图；未连接、失败或超时会抛异常。"""
    if not controller.connected:
        raise RuntimeError("控制器未连接")
    job = controller.post_screencap()
    deadline = time.monotonic() + _SCREENCAP_TIMEOUT
    while not job.done:
        if time.monotonic() >= deadline:
            raise TimeoutError(f"截图超时（{_SCREENCAP_TIMEOUT:.1f}s）")
        time.sleep(0.05)
    if not job.succeeded:
        raise RuntimeError(f"截图失败: {job.status}")
    return job.get()


class FreezeDetectAction(CustomAction):
    """检测游戏卡死。

    custom_action_param（JSON 字符串或对象）：
    - package: 包名，默认 com.fyf.newslggf
    - freeze_seconds: 画面持续无变化多久判定卡死，默认 60，最小 5
    - interval: 截图间隔秒数，默认 2，最小 0.2
    - timeout: 最长检测秒数，0 表示一直检测（默认）
    """

    def run(
        self,
        context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        cfg = self._load_param(argv.custom_action_param)
        package = str(cfg.get("package") or _DEFAULT_PACKAGE)
        freeze_seconds = max(_MIN_FREEZE_SECONDS, float(cfg.get("freeze_seconds", _DEFAULT_FREEZE_SECONDS)))
        interval = max(_MIN_INTERVAL, float(cfg.get("interval", _DEFAULT_INTERVAL)))
        timeout = max(0.0, float(cfg.get("timeout", 0.0)))

        controller = context.tasker.controller
        if not self._is_running(controller, package):
            logger.warning("进程不存在，判定为卡死: %s", package)
            return CustomAction.RunResult(success=True)

        logger.info(
            "开始卡死检测: package=%s, freeze_seconds=%s, interval=%s, timeout=%s",
            package,
            freeze_seconds,
            interval,
            timeout or "不限",
        )
        started = time.monotonic()
        last_change = started
        last_hash: bytes | None = None

        while True:
            if context.tasker.stopping:
                logger.info("任务已停止，结束卡死检测")
                return CustomAction.RunResult(success=False)
            if timeout and time.monotonic() - started >= timeout:
                logger.info("卡死检测超时，未发现卡死")
                return CustomAction.RunResult(success=False)

            try:
                image = _screencap(controller)
            except Exception:
                logger.exception("卡死检测截图失败")
                return CustomAction.RunResult(success=False)

            if not self._is_running(controller, package):
                logger.warning("进程已退出，判定为卡死: %s", package)
                return CustomAction.RunResult(success=True)

            now = time.monotonic()
            current_hash = self._hash_frame(image)
            if current_hash != last_hash:
                last_hash = current_hash
                last_change = now
            elif now - last_change >= freeze_seconds:
                logger.warning("画面已 %.1f 秒无变化，判定卡死: %s", now - last_change, package)
                return CustomAction.RunResult(success=True)

            time.sleep(interval)

    @staticmethod
    def _hash_frame(image) -> bytes:
        sample = image[::8, ::8]
        return hashlib.blake2b(sample.tobytes(), digest_size=8).digest()

    @staticmethod
    def _is_running(controller, package: str) -> bool:
        try:
            job = controller.post_shell(f"pidof {package}", timeout=5000)
            return bool((job.wait().get() or "").strip())
        except Exception:
            logger.exception("检查进程失败: %s", package)
            return True

    @staticmethod
    def _load_param(raw) -> dict:
        if isinstance(raw, dict):
            return raw
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            logger.warning("卡死检测参数非合法 JSON: %s", raw)
            return {}
        return data if isinstance(data, dict) else {}
