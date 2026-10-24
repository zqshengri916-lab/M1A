import atexit
import os
import subprocess
import sys
from pathlib import Path

# 必须在 import action 之前把项目根目录和 agent 目录加入 sys.path：
# action 下的模块会以 `agent.reco.xxx` 形式引用 reco 包
_AGENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _AGENT_DIR.parent
for _path in (str(_PROJECT_ROOT), str(_AGENT_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from maa.agent.agent_server import AgentServer
from maa.tasker import Tasker

import action
import reco
from loggerControl import LoggerControl

logger = LoggerControl(__name__).logger

_monitor_proc: subprocess.Popen | None = None


def _start_standalone_monitor() -> None:
    """通过 assert/start_monitor.bat 启动常驻监听子进程。"""
    global _monitor_proc
    launcher = _PROJECT_ROOT / "assert" / "start_monitor.bat"
    if not launcher.exists():
        logger.warning("未找到监听启动脚本: %s", launcher)
        return
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    env = os.environ.copy()
    env["M1A_AGENT_PID"] = str(os.getpid())
    try:
        _monitor_proc = subprocess.Popen(
            ["cmd.exe", "/c", str(launcher)],
            cwd=str(_PROJECT_ROOT),
            creationflags=creationflags,
            env=env,
        )
        logger.info("常驻监听子进程已启动: pid=%s", _monitor_proc.pid)
        atexit.register(_stop_standalone_monitor)
    except Exception:
        logger.exception("监听进程启动失败")


def _stop_standalone_monitor() -> None:
    proc = _monitor_proc
    if proc is None or proc.poll() is not None:
        return

    # cmd.exe 会再拉起 python 子进程，Windows 下需要按进程树结束
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        proc.terminate()

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


# .venv\Scripts\python.exe agent/main.py 149
# uv pip install --python "$env:APPDATA\uv\tools\maadebugger\Scripts\python.exe" "MaaFw==5.14.3"
# uv pip show --python "$env:APPDATA\uv\tools\maadebugger\Scripts\python.exe" MaaFw

def main():
    if len(sys.argv) > 1:
        socket_id = sys.argv[-1]
    else:
        socket_id = "error_socket_id"

    Tasker.set_log_dir('./')
    AgentServer.start_up(socket_id)
    print(f"agent的identifier注册为{socket_id}")

    _start_standalone_monitor()

    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    main()
