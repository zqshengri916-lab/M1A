import json
import time

from maa.custom_action import CustomAction

from loggerControl import LoggerControl
from utils import match_ocr

logger = LoggerControl(__name__).logger

_DEFAULT_PACKAGE = "com.fyf.newslggf"
_FOCUS_CMD = 'dumpsys window | grep -E "mCurrentFocus|mFocusedApp"'

# 弹窗提示区域；命中「点击任意」「空白」「关闭」中任意一个词即视为弹窗存在
_POPUP_ROI = [521, 477, 741, 209]
_POPUP_KEYWORDS = ("点击任意", "空白", "关闭")


class SinkAction(CustomAction):
    def run(
        self,
        context,
        argv:CustomAction.RunArg
    ) -> CustomAction.RunResult:
        
        while True:
            if match_ocr(context, roi=_POPUP_ROI, keywords=_POPUP_KEYWORDS):
                logger.info("正在关闭弹窗")
                context.tasker.controller.post_click(800, 660).wait()
                logger.info("弹窗已关闭")
                continue
            time.sleep(1)


class SinkAPP(CustomAction):
    """单次检查目标应用是否已启动，不等待。

    custom_action_param（JSON 字符串或对象）：
    - package: 包名，默认 com.fyf.newslggf
    - mode: process（进程存在，默认）/ foreground（处于前台）
    - on_running: stop（已启动时停止当前任务，默认）/ continue（仅继续流水线）
    """

    def run(
        self,
        context,
        argv: CustomAction.RunArg
    ) -> CustomAction.RunResult:
        cfg = self._load_param(argv.custom_action_param)
        package = str(cfg.get("package") or _DEFAULT_PACKAGE)
        mode = str(cfg.get("mode") or "process").lower()

        if not self._is_started(context.tasker.controller, package, mode):
            logger.info("应用未启动，继续流水线: %s", package)
            return CustomAction.RunResult(success=True)

        logger.info("应用已在运行: %s", package)
        if str(cfg.get("on_running") or "stop").lower() == "stop":
            # 不等待 post_stop，避免与当前动作互锁
            context.tasker.post_stop()
            logger.info("已停止当前任务")
        return CustomAction.RunResult(success=True)

    @staticmethod
    def _is_started(controller, package: str, mode: str) -> bool:
        if mode == "foreground":
            return package in SinkAPP._shell(controller, _FOCUS_CMD)
        return bool(SinkAPP._shell(controller, f"pidof {package}").strip())

    @staticmethod
    def _shell(controller, cmd: str) -> str:
        try:
            job = controller.post_shell(cmd, timeout=5000)
            return job.wait().get() or ""
        except Exception:
            logger.exception("执行 shell 失败: %s", cmd)
            return ""

    @staticmethod
    def _load_param(raw) -> dict:
        if isinstance(raw, dict):
            return raw
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            logger.warning("应用启动检查参数非合法 JSON: %s", raw)
            return {}
        return data if isinstance(data, dict) else {}
