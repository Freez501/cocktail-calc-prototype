import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from cocktail_calc.config import EVENTS_FILE


def _load_events() -> Dict:
    if not os.path.exists(EVENTS_FILE):
        return {}
    with open(EVENTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_events(events: Dict) -> None:
    os.makedirs(os.path.dirname(EVENTS_FILE), exist_ok=True)
    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)


def list_events() -> List[Dict]:
    events = _load_events()
    items = []
    for event_id, data in events.items():
        data["id"] = event_id
        items.append(data)
    items.sort(key=lambda x: x.get("date", ""), reverse=True)
    return items


def get_event(event_id: str) -> Optional[Dict]:
    events = _load_events()
    data = events.get(event_id)
    if data:
        data["id"] = event_id
    return data


def create_event(data: Dict) -> str:
    events = _load_events()
    event_id = str(uuid.uuid4())[:8]
    data["created_at"] = datetime.now().isoformat()
    events[event_id] = data
    _save_events(events)
    return event_id


def update_event(event_id: str, data: Dict) -> bool:
    events = _load_events()
    if event_id not in events:
        return False
    data["updated_at"] = datetime.now().isoformat()
    events[event_id] = data
    _save_events(events)
    return True


def delete_event(event_id: str) -> bool:
    events = _load_events()
    if event_id not in events:
        return False
    del events[event_id]
    _save_events(events)
    return True
