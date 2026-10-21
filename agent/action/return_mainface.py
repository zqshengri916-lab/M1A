from re import A
import time

from maa.custom_action import CustomAction

from reco.interface_reco import FaceReco

from loggerControl import LoggerControl
logger = LoggerControl(__name__).logger

class ReturnMainfaceAction(CustomAction):
    MAX_RETRY = 7

    def run(self, context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        facereco = FaceReco()
        for attempt in range(self.MAX_RETRY + 1):
            face_code = facereco.analyze(context)
            logger.info("返回主界面第 %s 次尝试，界面代码: %s", attempt + 1, face_code)

            if face_code == 101:
                time.sleep(0.2)
                return CustomAction.RunResult(success=True)
            elif face_code in (998, 102):
                context.tasker.controller.post_click(673, 17).wait()
                time.sleep(0.2)
            elif 200 < face_code <= 244:
                context.tasker.controller.post_click(73, 28).wait()
                time.sleep(0.3)
            elif face_code == 401:
                context.tasker.controller.post_click(1191, 305).wait()
                time.sleep(0.2)
                context.tasker.controller.post_click(73, 28).wait()
                time.sleep(0.5)
            elif face_code == 245:
                context.tasker.controller.post_click(72,655).wait()
                time.sleep(0.5)
        return CustomAction.RunResult(success=False)
