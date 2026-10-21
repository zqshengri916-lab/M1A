from pathlib import Path

from maa.pipeline import JOCR, JRecognitionType, JTemplateMatch
import numpy
from PIL import Image

from maa.context import Context
from maa.define import RecognitionDetail

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMP_PIC_DIR = _PROJECT_ROOT / "debug" / "logs" / "temp_pic"

_REA2D = [
        ["A", ""],
        ["B", ""],
        ["C", ""],
        ["D", ""],
        [" ", ""],
        ["\\?", "？"],
    ]

def get_detailbyocr(context: Context, roi, replace: list = _REA2D) -> RecognitionDetail | None:
    """根据 ROI 识别文本，使用 controller 的缓存截图。"""
    result = context.run_recognition_direct(
        JRecognitionType.OCR,
        JOCR(roi=roi, replace=replace),
        context.tasker.controller.cached_image,
    )
    if result is None:
        return None
    return result

def get_detailbyTemplate(context: Context, roi, template: str):
    """根据 ROI 识别模板，返回 (hit, box)。识别未启动时返回 (False, None)。"""
    result = context.run_recognition_direct(
        JRecognitionType.TemplateMatch,
        JTemplateMatch(roi=roi, template=template),
        context.tasker.controller.cached_image,
    )
    if result is None:
        return False, None
    return result.hit, result.box

def match_ocr(
    context: Context,
    text: str,
    roi: tuple = [480,587,349,132],
    replace: list = _REA2D) -> bool:
    """根据 ROI 识别文本，返回是否匹配。"""
    result = get_detailbyocr(context, roi, replace)
    if result is None:
        return False
    return result.best_result.text == text

def save_img(image, name: str = "temp.png") -> str | None:
    """保存截图到 logs/temp_pic，返回保存路径。失败或无图像时返回 None。"""
    if image is None:
        return None
    try:
        TEMP_PIC_DIR.mkdir(parents=True, exist_ok=True)
        if getattr(image, "ndim", 0) == 3 and image.shape[2] >= 3:
            # Maa 返回 BGR，转成 RGB
            pil = Image.fromarray(numpy.ascontiguousarray(image[:, :, ::-1]))
        else:
            pil = Image.fromarray(image)
        target = TEMP_PIC_DIR / name
        pil.save(target)
        return str(target)
    except Exception:
        return None
