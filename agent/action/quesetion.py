
import sys
from pathlib import Path
import json
import random
from datetime import datetime
from loggerControl import LoggerControl
from utils import get_detailbyocr, get_detailbyTemplate

from maa.custom_action import CustomAction

root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root))

class QuestionAction(CustomAction):
    BANK_PATH = root / "resource/question_bank.json"
    RIGHT = "operator/question/right.png"
    QUESTION_ROI = (259,302,788,133)
    OPTION_ROIS = {
        "A": (143, 462, 483, 51),
        "B": (658, 465, 469, 48),
        "C": (145, 538, 493, 49),
        "D": (660, 538, 470, 49),
    }
    OFFSET = [52, 7, 351, -13]
    logger = LoggerControl(__name__).logger
    try:
        with open(BANK_PATH, "r", encoding="utf-8") as f:
                bank:dict = json.load(f)
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
        # 刷新 controller 缓存截图（utils 内的识别读取 cached_image）
        context.tasker.controller.post_screencap().wait()

        question_detail = get_detailbyocr(context, self.QUESTION_ROI)
        question = question_detail.best_result.text if question_detail and question_detail.best_result else None
        if not question:
            self.logger.warning("题目文本识别失败，本次不作答")
            return CustomAction.RunResult(success=True)
        qusetion_r = next((q for q in self.bank["questions"] if q["question"] == question), {})
        answer = qusetion_r.get("answer")
        if answer is None:
            answer = random.choice(["A", "B", "C", "D"])
            self.logger.info(f"未检测到答案，随机选择答案: {answer}")
            context.tasker.controller.post_click(
                self.OPTION_ROIS[answer][0] + self.OPTION_ROIS[answer][2] // 2,
                self.OPTION_ROIS[answer][1] + self.OPTION_ROIS[answer][3] // 2,
            )
            #点击提交
            context.tasker.controller.post_click(636, 619)
            context.wait_freezes()
            context.tasker.controller.post_click(636, 619)
            box = get_detailbyTemplate(context, [141, 455, 1014, 138], self.RIGHT)[1]
            answer_detail = (
                get_detailbyocr(
                    context,
                    (
                        box[0] + self.OFFSET[0],
                        box[1] + self.OFFSET[1],
                        box[2] + self.OFFSET[2],
                        box[3] + self.OFFSET[3],
                    ),
                )
                if box is not None
                else None
            )
            answer_text = answer_detail.best_result.text if answer_detail and answer_detail.best_result else ""
            if answer_text:
                self.bank["questions"].append(
                    {
                        "question": question,
                        "answer": answer_text,
                        "count": 1,
                    }
                )
                self._save_bank()
            else:
                self.logger.warning("正确答案识别失败，未记录题库,尝试记录")
            return CustomAction.RunResult(success=True)
        self.selectRightAnswerAndsave(context, answer, qusetion_r)
        return CustomAction.RunResult(success=True)

    def _save_bank(self) -> None:
        """保存题库，写入前刷新 updated_at。"""
        self.bank["updated_at"] = datetime.now().isoformat(timespec="seconds")
        with open(self.BANK_PATH, "w", encoding="utf-8") as f:
            json.dump(self.bank, f, ensure_ascii=False, indent=4)

    def selectRightAnswerAndsave(self, context, answer, question_entry):
        A = get_detailbyocr(context, self.OPTION_ROIS["A"])
        B = get_detailbyocr(context, self.OPTION_ROIS["B"])
        C = get_detailbyocr(context, self.OPTION_ROIS["C"])
        D = get_detailbyocr(context, self.OPTION_ROIS["D"])
        for option in [A, B, C, D]:
            best = option.best_result if option is not None else None
            if best is not None and best.text == answer:
                context.tasker.controller.post_click(
                    best.box[0] + best.box[2] // 2,
                    best.box[1] + best.box[3] // 2,
                )
                self.logger.info(f"成功识别答案: {best.text}")
                context.tasker.controller.post_click(636, 619)
                context.wait_freezes()
                context.tasker.controller.post_click(636, 619)

                question_entry["count"] += 1
                self.bank["questions"] = sorted(self.bank["questions"], key = lambda x: x["count"], reverse=True)
                self._save_bank()
                self.logger.info("成功保存题库")
                return True
        return False
        