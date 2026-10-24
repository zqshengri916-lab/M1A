
import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from maa.custom_action import CustomAction

from loggerControl import LoggerControl
from utils import get_detailbyocr, get_detailbyTemplate

root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root))


class QuestionAction(CustomAction):
    BANK_PATH = root / "config/question_bank.json"
    RIGHT = "operator/question/right.png"
    QUESTION_ROI = (259, 302, 788, 133)
    OPTION_ROIS = {
        "A": (143, 462, 483, 51),
        "B": (658, 465, 469, 48),
        "C": (145, 538, 493, 49),
        "D": (660, 538, 470, 49),
    }
    OFFSET = [52, 7, 351, -13]
    # 点击提交后等待结算/正确答案出现的时间（秒）
    RESULT_WAIT = 1.5
    logger = LoggerControl(__name__).logger

    try:
        with open(BANK_PATH, "r", encoding="utf-8") as f:
            bank: dict = json.load(f)
    except FileNotFoundError:
        logger.error(f"题库文件不存在,请检查路径: {BANK_PATH}, 尝试创建文件")
        bank = {
            "version": 1,
            "updated_at": "2026-09-01T14:53:22",
            "questions": [
                {
                    "question": "费伊出生于精灵族的什么地方？",
                    "answer": "月辉之森",
                    "count": 0
                },
                {
                    "question": "哈娜触碰禁地前原本计划要做的事情是？",
                    "answer": "外出探险",
                    "count": 0
                }
            ],
            "help_stats": {
                "date": "",
                "count": 0
            }
        }

    def run(self, context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            # 刷新 controller 缓存截图（utils 内的识别读取 cached_image）
            self._refresh(context)

            question_detail = get_detailbyocr(context, self.QUESTION_ROI)
            question = question_detail.best_result.text if question_detail and question_detail.best_result else None
            if not question:
                self.logger.warning("题目文本识别失败，本次不作答")
                return CustomAction.RunResult(success=True)

            question_entry = next((q for q in self.bank["questions"] if q["question"] == question), {})
            answer = question_entry.get("answer")
            if answer is None:
                self._answer_unknown(context, question)
                return CustomAction.RunResult(success=True)

            self.selectRightAnswerAndsave(context, answer, question_entry)
            return CustomAction.RunResult(success=True)
        except Exception:
            # 自定义动作里的异常会被 ctypes 回调吞掉，这里显式记录
            self.logger.exception("答题动作异常")
            return CustomAction.RunResult(success=True)

    def _answer_unknown(self, context, question: str) -> None:
        """题库中没有该题：随机作答，提交后识别正确答案并入库。"""
        picked = random.choice(["A", "B", "C", "D"])
        self.logger.info(f"未检测到答案，随机选择答案: {picked}")
        roi = self.OPTION_ROIS[picked]
        self._click(context, roi[0] + roi[2] // 2, roi[1] + roi[3] // 2)

        # 提交答案
        self._click(context, 636, 619)
        time.sleep(self.RESULT_WAIT)
        # 关闭结算弹窗
        self._click(context, 636, 619)
        time.sleep(0.5)
        self._refresh(context)

        hit, box = get_detailbyTemplate(context, [141, 455, 1014, 138], self.RIGHT)
        self.logger.info("正确答案标记 right.png 命中=%s, box=%s", hit, box)
        if box is None:
            self.logger.warning("未识别到 right.png（可能是提交后未出现结算/答案区域变化）")
            return

        answer_detail = get_detailbyocr(
            context,
            (
                box[0] + self.OFFSET[0],
                box[1] + self.OFFSET[1],
                box[2] + self.OFFSET[2],
                box[3] + self.OFFSET[3],
            ),
        )
        answer_text = answer_detail.best_result.text if answer_detail and answer_detail.best_result else ""
        if not answer_text:
            self.logger.warning("正确答案文本识别失败，未记录题库")
            return

        self.bank["questions"].append(
            {
                "question": question,
                "answer": answer_text,
                "count": 1,
            }
        )
        self._save_bank()
        self.logger.info("新题已入库: %s -> %s", question, answer_text)

    def selectRightAnswerAndsave(self, context, answer, question_entry) -> bool:
        details = {key: get_detailbyocr(context, roi) for key, roi in self.OPTION_ROIS.items()}
        answer_key = self._norm(answer)
        for option, detail in details.items():
            best = detail.best_result if detail is not None else None
            if best is None:
                continue
            text = best.text or ""
            normalized = self._norm(text)
            if not normalized:
                continue
            if normalized == answer_key or answer_key in normalized or normalized in answer_key:
                self._click(
                    context,
                    best.box[0] + best.box[2] // 2,
                    best.box[1] + best.box[3] // 2,
                )
                self.logger.info(f"成功识别答案: {best.text} ({option})")

                self._click(context, 636, 619)
                time.sleep(self.RESULT_WAIT)
                self._click(context, 636, 619)

                question_entry["count"] = question_entry.get("count", 0) + 1
                self.bank["questions"] = sorted(
                    self.bank["questions"], key=lambda x: x.get("count", 0), reverse=True
                )
                self._save_bank()
                self.logger.info("成功保存题库")
                return True

        self.logger.warning("选项中没有匹配到答案: %r", answer)
        return False

    def _save_bank(self) -> None:
        """保存题库，写入前刷新 updated_at。"""
        self.bank["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.BANK_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(self.BANK_PATH, "w", encoding="utf-8") as f:
            json.dump(self.bank, f, ensure_ascii=False, indent=4)
        self.logger.info("题库已写入: %s (updated_at=%s)", self.BANK_PATH, self.bank["updated_at"])

    @staticmethod
    def _refresh(context) -> None:
        context.tasker.controller.post_screencap().wait()

    @staticmethod
    def _click(context, x: int, y: int) -> None:
        context.tasker.controller.post_click(x, y).wait()

    @staticmethod
    def _norm(text: str) -> str:
        return re.sub(r"[\s。，、？！,\.\?!:：;；\"'“”‘’()（）\[\]【】]", "", text or "")
