from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


def append_match_logs(entries: Iterable[dict]) -> None:
    log_path = Path(__file__).resolve().parents[3] / "logs" / "match_reason.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    default_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with log_path.open("a", encoding="utf-8") as handle:
            for entry in entries:
                timestamp = entry.get("timestamp") or default_timestamp
                level = entry.get("level") or "INFO"
                property_label = entry.get("property_label") or "-"
                group_name = entry.get("group_name") or "-"
                field = entry.get("field") or "-"
                result = entry.get("result") or "-"
                reason = entry.get("reason") or ""
                line = f"{level}：{timestamp} {property_label} {group_name} {field} {result} {reason}".strip()
                handle.write(line + "\n")
    except Exception:
        logger.exception("写入匹配日志失败")
