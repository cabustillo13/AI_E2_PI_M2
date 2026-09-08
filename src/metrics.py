import json
import os
from typing import Dict, Any


class MetricsTracker:
    def __init__(self, log_file: str = "data/metrics.jsonl"):
        self.log_file = log_file
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

    def log_event(self, event_name: str, payload: Dict[str, Any]):
        record = {
            "event": event_name,
            "data": payload
        }
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")