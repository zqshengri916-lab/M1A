"""
常驻监听进程：由 assert/start_monitor.bat 启动（agent/main.py 会拉起该 bat）。
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

_ASSERT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _ASSERT_DIR.parent
_AGENT_DIR = _PROJECT_ROOT / "agent"
for _path in (str(_PROJECT_ROOT), str(_AGENT_DIR), str(_ASSERT_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from maa.controller import AdbController  # noqa: E402
from maa.resource import Resource  # noqa: E402
from maa.tasker import Tasker  # noqa: E402

from loggerControl import LoggerControl  # noqa: E402
from monitor import MonitorConfig  # noqa: E402
from monitor_step import MonitorStepAction  # noqa: E402

logger = LoggerControl(__name__).logger

_CONFIG_PATH = _PROJECT_ROOT / "config" / "monitor.json"
_MXU_CONFIG = _PROJECT_ROOT / "config" / "mxu-M1A.json"
_RESOURCE_DIR = _PROJECT_ROOT / "resource" / "base"

_LOOP_ENTRY = "__monitor_loop__"
_STEP_ENTRY = "__monitor_step__"
_ACTION_NAME = "监听一次"


def _parent_alive(pid: int) -> bool:
    """判断父进程是否仍存活。"""
    if os.name == "nt":
        import ctypes

        synchronize = 0x00100000
        wait_timeout = 0x00000102
        handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, pid)
        if not handle:
            return False
        try:
            return ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == wait_timeout
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _start_parent_watchdog() -> None:
    """agent 被强制结束时，监听进程也自动退出。"""
    raw = os.environ.get("M1A_AGENT_PID", "").strip()
    if not raw.isdigit():
        return
    pid = int(raw)

    def loop() -> None:
        while True:
            time.sleep(2)
            if not _parent_alive(pid):
                logger.warning("agent 进程已退出，监听进程自动结束")
                os._exit(0)

    threading.Thread(target=loop, name="ParentWatchdog", daemon=True).start()
    logger.info("已启用父进程看护: agent pid=%s", pid)


def _load_settings() -> dict | None:
    if not _CONFIG_PATH.exists():
        logger.info("未找到 config/monitor.json，跳过常驻监听")
        return None
    try:
        settings = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("读取 config/monitor.json 失败")
        return None
    if not settings.get("enabled"):
        logger.info("config/monitor.json 中 enabled=false，跳过常驻监听")
        return None
    return settings


def _mxu_address() -> str:
    try:
        data = json.loads(_MXU_CONFIG.read_text(encoding="utf-8"))
        for instance in data.get("instances", []):
            address = (instance.get("savedDevice") or {}).get("adbDeviceAddress")
            if address:
                return str(address)
    except Exception:
        logger.exception("读取 MXU 配置失败")
    return ""


def _find_adb(settings: dict, address: str) -> str:
    adb_path = str(settings.get("adb_path") or "").strip()
    if adb_path:
        return adb_path
    try:
        from maa.toolkit import Toolkit

        for device in Toolkit.find_adb_devices():
            if not address or device.address == address:
                return str(device.adb_path)
    except Exception:
        logger.exception("自动搜索 ADB 设备失败")
    return ""


def _build_loop_pipeline(config: MonitorConfig, monitor_param) -> dict:
    """构造 `[JumpBack]` 常驻循环：loop -> step -> 回到 loop。"""
    return {
        _LOOP_ENTRY: {
            "recognition": {"type": "DirectHit"},
            "next": [f"[JumpBack]{_STEP_ENTRY}"],
        },
        _STEP_ENTRY: {
            "recognition": {"type": "DirectHit"},
            "action": {
                "type": "Custom",
                "param": {
                    "custom_action": _ACTION_NAME,
                    "custom_action_param": monitor_param,
                },
            },
            # 单轮截图 + OCR 约占 1 秒，post_delay 用来补齐配置的间隔
            "post_delay": max(0, int(config.interval * 1000) - 1000),
        },
    }


def start_monitor_task() -> None:
    _start_parent_watchdog()

    settings = _load_settings()
    if settings is None:
        return

    monitor_param = settings.get("monitor") or {"expected": "结算"}
    config = MonitorConfig.from_param(monitor_param)
    if config is None:
        logger.warning("常驻监听参数无效，已跳过: %s", monitor_param)
        return

    address = str(settings.get("address") or _mxu_address()).strip()
    adb_path = _find_adb(settings, address)
    if not adb_path or not address:
        logger.warning("常驻监听缺少 adb_path / address，已跳过")
        return

    resource = Resource()
    resource.post_bundle(str(_RESOURCE_DIR)).wait()
    if not resource.loaded:
        logger.error("常驻监听加载资源失败: %s", _RESOURCE_DIR)
        return

    controller = AdbController(adb_path, address, config=settings.get("controller_config"))
    if not controller.post_connection().wait().succeeded:
        logger.error("常驻监听连接设备失败: %s", address)
        return

    tasker = Tasker()
    tasker.bind(resource, controller)
    if not tasker.inited:
        logger.error("常驻监听 Tasker 初始化失败")
        return

    # 自建 Tasker 需要把动作注册到自己的 Resource 上
    resource.custom_action(_ACTION_NAME)(MonitorStepAction)

    pipeline = _build_loop_pipeline(config, monitor_param)
    logger.info(
        "常驻监听循环启动: expected=%r, keywords=%s, click=%s, interval=%ss @ %s",
        config.expected,
        config.keywords,
        config.click,
        config.interval,
        address,
    )
    tasker.post_task(_LOOP_ENTRY, pipeline).wait()
    logger.info("常驻监听循环已结束")


if __name__ == "__main__":
    start_monitor_task()
