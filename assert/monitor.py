"""
监听公共工具：参数解析、截图、OCR 匹配与点击。

监听运行在独立进程 assert/standalone.py 中（由 assert/start_monitor.bat 启动），
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

from maa.pipeline import JOCR

from loggerControl import LoggerControl

logger = LoggerControl(__name__).logger

# 轮询间隔（秒）：固定不低于 1 秒，避免高频截图 + OCR 造成资源开销
MIN_INTERVAL = 1.0
# 单次截图最长等待时间（秒），避免 job 卡死导致线程无响应
SCREENCAP_TIMEOUT = 5.0
_RESULT_POLL = 0.05


def load_param(raw: Any) -> dict[str, Any] | None:
    """把 JSON 字符串 / dict 统一成 dict；非法输入返回 None。"""
    if isinstance(raw, dict):
        return raw
    if not raw:
        return None
    if not isinstance(raw, str):
        logger.warning("监听参数类型不支持: %r", type(raw))
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("监听参数非合法 JSON: %s", raw)
        return None
    return parsed if isinstance(parsed, dict) else None


@dataclass
class MonitorConfig:
    """监听配置。"""

    expected: str
    interval: float = 1.0
    roi: list[int] | None = None
    keywords: tuple[str, ...] | None = None
    click: bool | str | list[int] = "hit"

    @classmethod
    def from_param(cls, raw: Any) -> MonitorConfig | None:
        """解析参数；expected 与 keywords 都为空时返回 None。"""
        cfg = load_param(raw)
        if cfg is None:
            return None

        expected = cfg.get("expected") or cfg.get("excepted")
        if isinstance(expected, (list, tuple)):
            expected = expected[0] if expected else ""
        expected = str(expected or "").strip()
        keywords = cls._parse_keywords(cfg.get("keywords"))
        if not expected:
            if not keywords:
                logger.warning("监听参数缺少 expected/keywords，已忽略: %s", raw)
                return None
            expected = keywords[0]

        return cls(
            expected=expected,
            interval=cls._parse_interval(cfg),
            roi=cls._parse_roi(cfg.get("roi")),
            keywords=keywords,
            click=cls._parse_click(cfg.get("click")),
        )

    @staticmethod
    def _parse_keywords(raw: Any) -> tuple[str, ...] | None:
        """解析关键词：支持列表或逗号/顿号/竖线分隔的字符串。"""
        if not raw:
            return None
        if isinstance(raw, str):
            parts = [part.strip() for part in re.split(r"[,，、|\s]+", raw) if part.strip()]
        elif isinstance(raw, (list, tuple)):
            parts = [str(part).strip() for part in raw if str(part).strip()]
        else:
            logger.warning("监听参数 keywords 非法: %r", raw)
            return None
        return tuple(parts) or None

    @staticmethod
    def _parse_roi(raw: Any) -> list[int] | None:
        if not raw:
            return None
        if isinstance(raw, (list, tuple)) and len(raw) == 4:
            try:
                return [int(value) for value in raw]
            except (TypeError, ValueError):
                pass
        logger.warning("监听参数 roi 非法: %r", raw)
        return None

    @staticmethod
    def _parse_click(raw: Any) -> bool | str | list[int]:
        """解析命中后的点击方式。

        - 缺省 / true / "hit"：点击命中框中心
        - [x, y] 或 "932,620"：点击固定坐标
        - false / "off"：不点击
        """
        if raw is None or raw is True:
            return "hit"
        if raw is False:
            return False
        if isinstance(raw, (list, tuple)):
            if len(raw) == 2:
                try:
                    return [int(raw[0]), int(raw[1])]
                except (TypeError, ValueError):
                    pass
            logger.warning("监听参数 click 非法: %r，改为点击命中框中心", raw)
            return "hit"
        if isinstance(raw, str):
            value = raw.strip().lower()
            if value in ("", "hit", "center"):
                return "hit"
            if value in ("false", "off", "none"):
                return False
            match = re.fullmatch(r"\s*(\d+)\s*[,，]\s*(\d+)\s*", raw)
            if match:
                return [int(match.group(1)), int(match.group(2))]
        logger.warning("监听参数 click 非法: %r，改为点击命中框中心", raw)
        return "hit"

    @staticmethod
    def _parse_interval(cfg: dict[str, Any]) -> float:
        """解析轮询间隔，并限制为不低于 MIN_INTERVAL 秒。"""
        raw = cfg.get("interval", MIN_INTERVAL)
        try:
            interval = float(raw)
        except (TypeError, ValueError):
            logger.warning("监听参数 interval 非法，使用默认 %ss: %r", MIN_INTERVAL, raw)
            return MIN_INTERVAL
        if interval < MIN_INTERVAL:
            logger.warning("监听间隔 %ss 过小，已调整为 %ss", interval, MIN_INTERVAL)
            return MIN_INTERVAL
        return interval


def screencap(controller):
    """同步截图；未连接、失败或超时会抛异常。"""
    if not controller.connected:
        raise RuntimeError("控制器未连接")
    job = controller.post_screencap()

    deadline = time.monotonic() + SCREENCAP_TIMEOUT
    while not job.done:
        if time.monotonic() >= deadline:
            raise TimeoutError(f"截图超时（{SCREENCAP_TIMEOUT:.1f}s）")
        time.sleep(_RESULT_POLL)

    if not job.succeeded:
        raise RuntimeError(f"截图失败: {job.status}")
    return job.get()


def build_ocr_param(config: MonitorConfig) -> JOCR:
    """按配置构造 OCR 参数。"""
    param = JOCR(expected=[] if config.keywords else [config.expected])
    if config.roi:
        param.roi = tuple(config.roi)
    return param


def match_text(detail, config: MonitorConfig) -> tuple[str | None, list[int] | None]:
    """从识别结果中取命中文本与框。"""
    if detail is None:
        return None, None

    texts = [getattr(item, "text", "") or "" for item in (detail.all_results or [])]
    logger.debug("监听 OCR 原文: %s", texts[:5])

    if config.keywords:
        for item in detail.all_results or []:
            text = getattr(item, "text", "") or ""
            if any(keyword in text for keyword in config.keywords):
                return text, getattr(item, "box", None)
        return None, None

    if not detail.hit or detail.best_result is None:
        return None, None

    best = detail.best_result
    return (getattr(best, "text", "") or config.expected), best.box


def click(context, target: bool | str | list[int], box: list[int] | None) -> None:
    """执行点击：命中框中心 / 固定坐标 / 不点击。"""
    if target is False:
        return
    if target == "hit":
        if not box or len(box) < 4:
            logger.warning("监听命中但无有效识别框，跳过点击")
            return
        x = int(box[0] + box[2] // 2)
        y = int(box[1] + box[3] // 2)
    else:
        x, y = int(target[0]), int(target[1])

    try:
        context.tasker.controller.post_click(x, y).wait()
        logger.info("监听命中后点击: (%s, %s)", x, y)
    except Exception:
        logger.exception("监听命中后点击失败: (%s, %s)", x, y)
