from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy
from PIL import Image

from loggerControl import LoggerControl
from utils import get_detailbyocr, get_detailbyTemplate

logger = LoggerControl(__name__).logger


def _to_pil_image(image: numpy.ndarray) -> Image.Image:
    """把 Maa 的 BGR ndarray 转成 PIL Image。"""
    if image.ndim == 3 and image.shape[2] >= 3:
        rgb = numpy.ascontiguousarray(image[:, :, ::-1])
        return Image.fromarray(rgb)
    return Image.fromarray(image)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AWARD_IMAGE_DIR = PROJECT_ROOT / "resource" / "base" / "image" / "award"
TEMP_PIC_DIR = PROJECT_ROOT / "logs" / "temp_pic"

INITIAL_SCREENSHOT_NAME = "初始_最近获取道具截图.png"
AFTER_SWIPE_SCREENSHOT_NAME = "拖动后_最近获取道具截图.png"

INCREMENT_OCR_OFFSET = (-13, -13, 33, 36)
INCREMENT_OCR_REPLACE = [
    [" ", ""],
    ["\n", ""],
    ["\r", ""],
    ["，", ""],
    [",", ""],
]

SCREENSHOT_SIZE = (836, 225)

_SWIPE_CONFIG: dict[str, dict[str, Any]] = {
    "left": {
        "steps": 3,
        "wait_seconds": 0.7,
        "from": (int(SCREENSHOT_SIZE[0] * 0.85), int(SCREENSHOT_SIZE[1] * 0.5)),
        "to": (int(SCREENSHOT_SIZE[0] * 0.15), int(SCREENSHOT_SIZE[1] * 0.5)),
    },
    "up": {
        "steps": 3,
        "wait_seconds": 0.7,
        "from": (int(SCREENSHOT_SIZE[0] * 0.5), int(SCREENSHOT_SIZE[1] * 0.8)),
        "to": (int(SCREENSHOT_SIZE[0] * 0.5), int(SCREENSHOT_SIZE[1] * 0.15)),
    },
}


@dataclass
class IncrementItem:
    item_name: str
    count: int
    template_box: tuple[int, int, int, int]
    ocr_box: tuple[int, int, int, int]


class AwardFace:
    _template_cache: dict[str, numpy.ndarray] = {}

    def __init__(self, award_image_dir: Path | None = None) -> None:
        self.award_image_dir = Path(award_image_dir or AWARD_IMAGE_DIR)
        self._templates: dict[str, Path] = {}
        if self.award_image_dir.exists():
            for p in sorted(self.award_image_dir.glob("*.png")):
                self._templates[p.stem] = p
        TEMP_PIC_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(
            "award templates loaded: count=%s, names=%s, temp_pic_dir=%s",
            len(self._templates),
            list(self._templates.keys()),
            TEMP_PIC_DIR,
        )

    @property
    def template_names(self) -> list[str]:
        return list(self._templates.keys())

    def detect_all(
        self,
        context,
        roi: tuple[int, int, int, int] | None = None,
        scroll_direction: str = "left",
    ) -> dict[str, IncrementItem]:
        if scroll_direction not in _SWIPE_CONFIG:
            logger.warning(
                "unknown scroll_direction=%s, fallback to left",
                scroll_direction,
            )
            scroll_direction = "left"

        effective_roi = self._validate_roi(roi)
        logger.info(
            "start detect_all: roi=%s, scroll=%s",
            effective_roi,
            scroll_direction,
        )

        results: dict[str, IncrementItem] = {}
        seen_positions: dict[str, tuple[int, int, int, int]] = {}

        swipe_cfg = _SWIPE_CONFIG[scroll_direction]
        total_steps = int(swipe_cfg["steps"])
        for step_idx in range(total_steps + 1):
            items, image = self._detect_once(
                context,
                effective_roi,
            )
            if image is not None:
                self._save_temp_screenshot(image, step_idx)

            for name, item in items.items():
                box = item.template_box
                dedup_key = (box[0] // 8, box[1] // 8)
                prev = seen_positions.get(name)
                if prev is not None:
                    prev_key = (prev[0] // 8, prev[1] // 8)
                    if prev_key == dedup_key:
                        continue
                seen_positions[name] = box
                results[name] = item
                logger.info(
                    "detected award item=%s count=%s icon=%s ocr=%s",
                    name,
                    item.count,
                    item.template_box,
                    item.ocr_box,
                )

            if step_idx < total_steps:
                logger.info(
                    "swipe screen direction=%s step=%s/%s",
                    scroll_direction,
                    step_idx + 1,
                    total_steps,
                )
                self._swipe(context, swipe_cfg)

        logger.info("detect_all finish total_items=%s", len(results))
        return results

    def _detect_once(
        self,
        context,
        roi: tuple[int, int, int, int],
    ) -> tuple[dict[str, IncrementItem], numpy.ndarray | None]:
        # 主动截图刷新 controller 缓存（utils 内的识别均读取该缓存图）
        image = context.tasker.controller.post_screencap().wait().get()
        if image is None:
            logger.error("screencap failed")
            return {}, None

        output: dict[str, IncrementItem] = {}
        for item_name, template_path in self._templates.items():
            template_rel = self._to_image_relative(template_path)
            if not template_rel:
                continue
            hit, box = get_detailbyTemplate(context, roi, [template_rel])
            if not hit or box is None:
                continue
            template_box = tuple(box)
            logger.debug("TemplateMatch hit name=%s box=%s", item_name, template_box)
            ocr_box = self._offset_box(template_box, INCREMENT_OCR_OFFSET)
            count = self._ocr_count(context, ocr_box)
            output[item_name] = IncrementItem(
                item_name=item_name,
                count=count,
                template_box=template_box,
                ocr_box=ocr_box,
            )
        return output, image

    def _ocr_count(
        self,
        context,
        ocr_roi: tuple[int, int, int, int],
    ) -> int:
        result = get_detailbyocr(context, ocr_roi, INCREMENT_OCR_REPLACE)
        best = getattr(result, "best_result", None) if result is not None else None
        raw = getattr(best, "text", "") or ""
        if not raw:
            logger.debug("OCR got empty text roi=%s", ocr_roi)
            return 0
        value = self._parse_count_text(raw)
        logger.debug("OCR roi=%s raw=%s parsed=%s", ocr_roi, raw, value)
        return value

    @staticmethod
    def _parse_count_text(text: str) -> int:
        text = text.strip()
        if not text:
            return 0
        wan_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*万", text)
        if wan_match:
            try:
                num = float(wan_match.group(1))
                return int(num * 10000)
            except ValueError:
                pass
        digits = re.findall(r"[0-9]+", text)
        if not digits:
            return 0
        try:
            return int("".join(digits))
        except ValueError:
            return 0

    @staticmethod
    def _offset_box(
        base: tuple[int, int, int, int],
        offset: tuple[int, int, int, int],
    ) -> tuple[int, int, int, int]:
        return (
            base[0] + offset[0],
            base[1] + offset[1],
            base[2] + offset[2],
            base[3] + offset[3],
        )

    @staticmethod
    def _validate_roi(
        roi: tuple[int, int, int, int] | None,
    ) -> tuple[int, int, int, int]:
        if roi is None:
            return (0, 0, SCREENSHOT_SIZE[0], SCREENSHOT_SIZE[1])
        if len(roi) >= 4:
            w, h = int(roi[2]), int(roi[3])
            if w > 0 and h > 0:
                return (int(roi[0]), int(roi[1]), w, h)
        return (0, 0, SCREENSHOT_SIZE[0], SCREENSHOT_SIZE[1])

    def _to_image_relative(self, template_path: Path) -> str:
        image_root = self.award_image_dir.parent
        try:
            rel = template_path.relative_to(image_root).as_posix()
            if rel.startswith("award/"):
                return rel
            return f"award/{template_path.name}"
        except ValueError:
            return f"award/{template_path.name}"

    @staticmethod
    def _swipe(context, cfg: dict[str, Any]) -> None:
        sx, sy = cfg["from"]
        ex, ey = cfg["to"]
        context.tasker.controller.post_swipe(sx, sy, ex, ey, 400).wait()
        wait_s = float(cfg.get("wait_seconds", 0.7))
        if wait_s > 0:
            time.sleep(wait_s)

    def _save_temp_screenshot(self, image: numpy.ndarray, step_idx: int) -> None:
        try:
            if step_idx <= 0:
                target = TEMP_PIC_DIR / INITIAL_SCREENSHOT_NAME
            else:
                target = TEMP_PIC_DIR / AFTER_SWIPE_SCREENSHOT_NAME
            TEMP_PIC_DIR.mkdir(parents=True, exist_ok=True)
            pil = _to_pil_image(image)
            pil.save(target, format="PNG")
            logger.debug(
                "saved temp screenshot step=%s -> %s",
                step_idx,
                target,
            )
        except Exception as exc:
            logger.warning("保存临时截图失败 step=%s: %s", step_idx, exc)
