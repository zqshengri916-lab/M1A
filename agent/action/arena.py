import json
from pathlib import Path
from typing import Any

from maa.custom_action import CustomAction
from maa.agent.agent_server import AgentServer

from loggerControl import LoggerControl
from utils import get_detailbyocr

MC_ROI = [610, 412, 609, 32]
MC_OFFSET = [-8, -1, 10, -2]
NAME_ROI = [598, 366, 637, 46]
MC_REPLACE = [[",", ""], ["，", ""], [" ", ""], ["\n", ""]]
NAME_REPLACE = [[" ", ""], ["\n", ""]]

logger = LoggerControl(__name__).logger

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ARENA_CONFIG_PATH = _PROJECT_ROOT / "resource" / "accout_date" / "arena_actlist.json"


def _load_config() -> dict[str, Any]:
    if not _ARENA_CONFIG_PATH.exists():
        logger.error("竞技场配置不存在: %s", _ARENA_CONFIG_PATH)
        return {}
    try:
        return json.loads(_ARENA_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("竞技场配置读取失败: %s", exc)
        return {}


def _text_to_int(text: str) -> int | None:
    """取出文本中的数字，无法解析返回 None。"""
    digits = "".join(ch for ch in str(text) if ch.isdigit())
    if not digits:
        return None
    return int(digits)


def _ocr_all(context, roi, replace) -> list:
    """识别 ROI 内的全部文本，返回识别结果列表（复用 utils.get_detailbyocr）。"""
    detail = get_detailbyocr(context, roi, replace)
    if detail is None:
        return []
    return list(detail.all_results or [])


@AgentServer.custom_action("选择战斗对象")
class ArenaAction(CustomAction):
    def run(self, context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        config = _load_config()
        cfg_type = str(config.get("type", "")).strip().upper()
        if not cfg_type:
            logger.error("resource/accout_date/arena_actlist.json 缺少 type 字段")
            return False

        if cfg_type == "CLOSE":
            results = _ocr_all(context, MC_ROI, MC_REPLACE)
            min_MC = self._compareByMC(results, int(config.get("Max_MC", 0) or 0))
            if min_MC is None:
                logger.warning("未检测到战力信息")
                logger.info("尝试重新进入竞技场")
                return False
            box = min_MC.box
            cx = box[0] + MC_OFFSET[0] + (box[2] + MC_OFFSET[2]) // 2
            cy = box[1] + MC_OFFSET[1] + (box[3] + MC_OFFSET[3]) // 2
            context.tasker.controller.post_click(cx, cy)
            logger.info("选择战力最小的 %s 对象", min_MC.text)
            return True

        if cfg_type not in {"WHITE", "BLACK"}:
            logger.error("resource/accout_date/arena_actlist.json 内的 type 字段出现错误: %s", cfg_type)
            return False

        actlist = config.get("actlist")
        if not isinstance(actlist, list):
            actlist = []
        actlist = [str(x).strip() for x in actlist if str(x).strip()]

        results = _ocr_all(context, NAME_ROI, NAME_REPLACE)

        if cfg_type == "WHITE":
            enable_select = [item for item in results if (item.text or "").strip() in actlist]
            if not enable_select:
                logger.info("未检测到可选择的对象,尝试刷新")
                context.tasker.controller.post_click(1207, 120)
                return False
            target = enable_select[0]
        else:
            disable_select = [item for item in results if (item.text or "").strip() not in actlist]
            if not disable_select:
                logger.info("未检测到可选择的对象,尝试刷新")
                context.tasker.controller.post_click(1207, 120)
                return False
            target = disable_select[0]

        box = target.box
        context.tasker.controller.post_click(
            box[0] + box[2] // 2,
            box[1] + box[3] // 2,
        )
        logger.info("选择 %s 对象", target.text)
        return True

    def _compareByMC(self, MC_lists: list, Max_MC: int):
        """
        比较战力大小，返回最小战力的对象
        """
        parsed: list[tuple[int, Any]] = []
        for item in MC_lists:
            value = _text_to_int(getattr(item, "text", ""))
            if value is not None:
                parsed.append((value, item))
        if not parsed:
            logger.error("未检测到战力信息")
            return None

        sorted_lists = [item for _, item in sorted(parsed, key=lambda x: x[0])]
        if Max_MC > 0:
            for candidate in sorted_lists[:3]:
                value = _text_to_int(getattr(candidate, "text", ""))
                if value is not None and value < Max_MC:
                    return candidate
        return sorted_lists[0]

