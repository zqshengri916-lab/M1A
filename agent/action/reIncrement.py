from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from loggerControl import LoggerControl
from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction

from reco.award_face import AwardFace

logger = LoggerControl(__name__).logger

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RECORD_PATH = PROJECT_ROOT / "resource" / "recordIncrement.json"

DEFAULT_ROI_KEY = "roi"
DEFAULT_SCROLL_KEY = "scroll_direction"


@AgentServer.custom_action("记录物品增量")
class RecordIncrementAction(CustomAction):
    def run(self, context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        raw = str(argv.custom_action_param or "")
        params: dict[str, Any] = {}
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    params = parsed
            except json.JSONDecodeError:
                logger.warning("custom_action_param 非合法 JSON，使用默认参数: %s", raw)

        roi = self._parse_roi(params.get(DEFAULT_ROI_KEY))
        scroll = str(params.get(DEFAULT_SCROLL_KEY, "left")).lower() or "left"

        detector = AwardFace()
        if roi is None:
            logger.info("开始记录物品增量: roi=全屏, scroll=%s", scroll)
        else:
            logger.info("开始记录物品增量: roi=%s, scroll=%s", roi, scroll)

        detected = detector.detect_all(
            context,
            roi=roi,
            scroll_direction="left" if scroll != "up" else "up",
        )

        record = self._load_record()
        self._merge_counts(record, detector, detected)
        self._save_record(record)
        logger.info(
            "记录完成: items_in_record=%s, detected=%s",
            len(record.get("items", {})),
            len(detected),
        )
        return True

    def _now_iso(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _empty_record(self) -> dict[str, Any]:
        return {
            "version": 1,
            "updated_at": "",
            "items": {},
        }

    def _normalize_record(self, data: Any) -> dict[str, Any]:
        record = self._empty_record()
        if isinstance(data, dict):
            if isinstance(data.get("items"), dict):
                cleaned: dict[str, Any] = {}
                for key, value in data["items"].items():
                    if not isinstance(key, str) or not key:
                        continue
                    if isinstance(value, (int, float)):
                        cleaned[key] = {
                            "last_count": int(value),
                            "last_increment": 0,
                            "first_seen_at": "",
                            "last_updated_at": "",
                            "history": [],
                        }
                    elif isinstance(value, dict):
                        entry = {
                            "last_count": int(value.get("last_count", 0) or 0),
                            "last_increment": int(value.get("last_increment", 0) or 0),
                            "first_seen_at": str(value.get("first_seen_at", "") or ""),
                            "last_updated_at": str(value.get("last_updated_at", "") or ""),
                        }
                        history = value.get("history")
                        if isinstance(history, list):
                            entry["history"] = [
                                h for h in history if isinstance(h, dict)
                            ][-200:]
                        else:
                            entry["history"] = []
                        cleaned[key] = entry
                record["items"] = cleaned
            record["version"] = int(data.get("version", 1) or 1)
            record["updated_at"] = str(data.get("updated_at", "") or "")
        return record

    def _load_record(self) -> dict[str, Any]:
        if not RECORD_PATH.exists():
            RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
            record = self._empty_record()
            self._save_record(record)
            return record
        try:
            raw = RECORD_PATH.read_text(encoding="utf-8")
            if not raw.strip():
                data = {}
            else:
                data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("recordIncrement.json 读取/解析失败，已回退空记录: %s", exc)
            data = {}
        return self._normalize_record(data)

    def _save_record(self, record: dict[str, Any]) -> None:
        normalized = self._normalize_record(record)
        if not normalized.get("updated_at"):
            normalized["updated_at"] = self._now_iso()
        RECORD_PATH.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _merge_counts(self, record: dict[str, Any], detector: AwardFace, detected: dict[str, Any]) -> None:
        items: dict[str, Any] = record.setdefault("items", {})
        now = self._now_iso()

        for name in detector.template_names:
            entry: dict[str, Any]
            if name in items:
                entry = items[name]
                if "first_seen_at" not in entry or not entry["first_seen_at"]:
                    entry["first_seen_at"] = now
                if "history" not in entry or not isinstance(entry["history"], list):
                    entry["history"] = []
            else:
                entry = {
                    "last_count": 0,
                    "last_increment": 0,
                    "first_seen_at": now,
                    "last_updated_at": "",
                    "history": [],
                }
                items[name] = entry
                logger.info("新增未被模板匹配到的物品记录: %s", name)

            item = detected.get(name)
            if item is None:
                continue
            current_count = int(getattr(item, "count", 0) or 0)
            prev_count = int(entry.get("last_count", 0) or 0)
            increment = current_count - prev_count if entry.get("last_updated_at") else current_count
            entry["last_count"] = current_count
            entry["last_increment"] = increment
            entry["last_updated_at"] = now
            history = entry["history"]
            history.append(
                {
                    "time": now,
                    "count": current_count,
                    "increment": increment,
                    "box": list(getattr(item, "template_box", (0, 0, 0, 0))),
                }
            )
            if len(history) > 200:
                entry["history"] = history[-200:]
            logger.info(
                "物品 %s 更新: prev=%s current=%s increment=%s",
                name,
                prev_count,
                current_count,
                increment,
            )

        record["updated_at"] = now

    def _parse_roi(self, param: Any) -> tuple[int, int, int, int] | None:
        if not isinstance(param, (list, tuple)) or len(param) < 4:
            return None
        try:
            roi = (int(param[0]), int(param[1]), int(param[2]), int(param[3]))
        except (TypeError, ValueError):
            return None
        if roi[2] <= 0 or roi[3] <= 0:
            return None
        return roi
