from maa.custom_action import CustomAction
from loggerControl import LoggerControl
from utils import match_ocr
import time

logger = LoggerControl(__name__).logger

class SinkAction(CustomAction):
    def run(
        self,
        context,
        argv:CustomAction.RunArg
    ) -> CustomAction.RunResult:
        
        while True:
            if match_ocr(context, "点击任意空白处关闭"):
                logger.info("正在关闭弹窗")
                context.tasker.controller.post_click(800, 660).wait()
                logger.info("弹窗已关闭")
                continue
            time.sleep(1)
        
