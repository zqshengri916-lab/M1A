"""
监听单步动作：截图 + OCR + 命中点击，始终返回成功。
"""

from maa.custom_action import CustomAction
from maa.pipeline import JRecognitionType

from loggerControl import LoggerControl
from monitor import MonitorConfig, build_ocr_param, click, match_text, screencap

logger = LoggerControl(__name__).logger


class MonitorStepAction(CustomAction):
    def run(
        self,
        context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        config = MonitorConfig.from_param(argv.custom_action_param)
        if config is None:
            return CustomAction.RunResult(success=True)

        try:
            image = screencap(context.tasker.controller)
            detail = context.run_recognition_direct(
                JRecognitionType.OCR,
                build_ocr_param(config),
                image,
            )
            text, box = match_text(detail, config)
            if text:
                logger.info("监听命中: %r", text)
                click(context, config.click, box)
        except Exception:
            logger.exception("监听识别失败")

        return CustomAction.RunResult(success=True)
