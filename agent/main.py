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
from maa.toolkit import Toolkit

import action
import reco
# .venv\Scripts\python.exe agent/main.py 149
# uv pip install --python "$env:APPDATA\uv\tools\maadebugger\Scripts\python.exe" "MaaFw==5.14.3"
# uv pip show --python "$env:APPDATA\uv\tools\maadebugger\Scripts\python.exe" MaaFw

def main():
    if len(sys.argv) > 1:
        socket_id = sys.argv[-1]
    else:
        socket_id = "error_socket_id"

    Toolkit.init_option('./')
    AgentServer.start_up(socket_id)
    print(f"agent的identifier注册为{socket_id}")
    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    main()
