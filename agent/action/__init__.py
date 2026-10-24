from maa.agent.agent_server import AgentServer

from . import arena
from . import reIncrement
from . import return_mainface
from . import stop_tasker
from . import watchdog
from .quesetion import QuestionAction
from .sink import SinkAPP, SinkAction


@AgentServer.custom_action("返回主界面")
class ReturnMainface(return_mainface.ReturnMainfaceAction):
    pass

@AgentServer.custom_action("回答问题")
class SelectAnswerAction(QuestionAction):
    pass

@AgentServer.custom_action("关闭弹窗")
class ClosePopupAction(SinkAction):
    pass

@AgentServer.custom_action("应用启动检查")
class CheckAppStart(SinkAPP):
    pass

@AgentServer.custom_action("卡死检测")
class FreezeDetect(watchdog.FreezeDetectAction):
    pass
