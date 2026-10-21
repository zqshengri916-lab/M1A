import json
import time

from maa.custom_recognition import CustomRecognition
from maa.pipeline import JOCR, JRecognitionType

from loggerControl import LoggerControl

logger = LoggerControl(__name__).logger

_DEFAULT_MAX_CNT = 10
_DEFAULT_START_SLEEP = 2.0
_DEFAULT_CUR_SLEEP = 0.5


class SinkRecognition(CustomRecognition):
    """轮询截图等待指定文本出现：命中返回识别框，超时返回 box=None。"""

    def analyze(
        self,
        context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        text, max_cnt, start_sleep, cur_sleep = self._parse_param(argv.custom_recognition_param)
        logger.info(
            "开始识别监听: expected=%r, max_cnt=%s, start_sleep=%s, cur_sleep=%s",
            text,
            max_cnt,
            start_sleep,
            cur_sleep,
        )

        if start_sleep > 0:
            time.sleep(start_sleep)

        for _ in range(max(1, max_cnt)):
            img = context.tasker.controller.post_screencap().wait().get()
            detail = context.run_recognition_direct(
                JRecognitionType.OCR,
                JOCR(expected=[text] if text else []),
                img,
            )
            best = detail.best_result if detail is not None and detail.hit else None
            if best is not None:
                found = getattr(best, "text", "")
                logger.info("识别监听命中: %s", found)
                return CustomRecognition.AnalyzeResult(
                    box=best.box,
                    detail={"expected": text, "text": found},
                )
            if cur_sleep > 0:
                time.sleep(cur_sleep)

        logger.warning("识别监听超时: expected=%r", text)
        return CustomRecognition.AnalyzeResult(
            box=None,
            detail={"expected": text, "timeout": True},
        )

    @staticmethod
    def _parse_param(raw) -> tuple[str, int, float, float]:
        """解析 custom_recognition_param（JSON 字符串），解析失败回退默认值。"""
        text = ""
        max_cnt: int = _DEFAULT_MAX_CNT
        start_sleep: float = _DEFAULT_START_SLEEP
        cur_sleep: float = _DEFAULT_CUR_SLEEP

        if not raw:
            return text, max_cnt, start_sleep, cur_sleep
        try:
            cfg = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            logger.warning("custom_recognition_param 非合法 JSON，使用默认参数: %s", raw)
            return text, max_cnt, start_sleep, cur_sleep
        if not isinstance(cfg, dict):
            return text, max_cnt, start_sleep, cur_sleep

        # 兼容历史拼写 excepted
        text = str(cfg.get("expected") or cfg.get("excepted") or "")
        max_cnt = int(cfg.get("max_cnt") or max_cnt)
        if cfg.get("start_sleep") is not None:
            start_sleep = float(cfg["start_sleep"])
        if cfg.get("cur_sleep") is not None:
            cur_sleep = float(cfg["cur_sleep"])
        return text, max_cnt, start_sleep, cur_sleep
