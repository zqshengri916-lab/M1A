from __future__ import annotations

from loggerControl import LoggerControl
from utils import get_detailbyocr

FULL_FACE: dict[str, int] = {
    "设置": 201,
    "领主时装": 202,
    "领主": 203,
    "增加天赋加点": 204,
    "装扮": 205,
    "转换角色性别": 206,
    "我的庄园": 207,
    "市政办公室": 208,
    "成就": 209,
    "道具宝鉴": 210,
    "英雄宝鉴": 211,
    "排行榜": 212,
    "英雄皮肤收集": 213,
    "天赋力": 214,
    "任务": 215,
    "科技": 216,
    "招募": 217,
    "制造": 218,
    "邮件": 219,
    "联盟中心": 220,
    "英雄": 221,
    "编队": 222,
    "召唤": 223,
    "背包": 224,
    "技能库": 225,
    "冒险": 226,
    "竞技": 227,
    "盛宴": 228,
    "交易所": 229,
    "市场": 230,
    "活动": 231,
    "商城": 232,
    "藏宝洞": 233,
    "记忆空间": 234,
    "荒原": 235,
    "遗迹": 236,
    "领主考核": 237,
    "挑战领主": 239,
    "深渊": 240,
    "世界首领": 241,
    "世界首领-个人版": 242,
    "魔法园": 243,
    "世界地图": 244,
    
    "大世界": 245,
}

ELSE_FACE: dict[str, int] = {
    "加载": 999,
    "其他": 998,
    "登录": 1,
    "角色列表": 2,
    "主界面": 101,
    "角色": 102,
    "资源转换": 301,
    "兑换码": 302,
    "bug反馈": 303,
    "好友": 304,
    "聊天": 305,
    "建造": 306,
    "特产运输": 307,
    "知识问答": 401,
}

logger = LoggerControl(__name__).logger


def _ocr_text(context, roi) -> str:
    """识别 ROI 内的文本，无结果时返回空字符串。"""
    detail = get_detailbyocr(context, roi)
    if detail is None or detail.best_result is None:
        return ""
    return detail.best_result.text


class FaceReco:
    def analyze(self, context) -> int:
        if context.tasker.controller.cached_image is None:
            logger.error("截图失败，无法识别界面")
            return 998
        text = _ocr_text(context, (103, 139, 59, 42))
        if "任务" in text:
            return 101

        if "城市" in _ocr_text(context, (42,666,70,43)):
            return 245

        text_full = _ocr_text(context, (58, 16, 297, 43))
        for face, code in FULL_FACE.items():
            if face in text_full:
                logger.info("界面识别: %s (代码 %s)", face, code)
                return code

        

        if "幻想广场" in text_full:
            text2 = _ocr_text(context, (634, 133, 103, 39))
            if "正确奖励" in text2:
                return 401
            return 238

        return 998
