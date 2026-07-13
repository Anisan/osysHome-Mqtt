"""MQTT topic persistence and property-link synchronization."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from app.core.lib.plugin_binding import remove_property_link, sync_property_link
from app.database import db, get_now_to_utc
from plugins.Mqtt.models.Mqtt import Topic

PLUGIN_NAME = "Mqtt"

_TOPIC_FIELDS = (
    "title",
    "path",
    "path_write",
    "linked_object",
    "linked_property",
    "linked_method",
    "qos",
    "retain",
    "replace_list",
    "readonly",
    "only_new_value",
    "value",
)


def topic_to_dict(topic: Topic) -> Dict[str, Any]:
    return {
        "id": topic.id,
        "title": topic.title,
        "path": topic.path,
        "path_write": topic.path_write,
        "linked_object": topic.linked_object,
        "linked_property": topic.linked_property,
        "linked_method": topic.linked_method,
        "qos": topic.qos,
        "retain": bool(topic.retain),
        "replace_list": topic.replace_list,
        "readonly": bool(topic.readonly),
        "only_new_value": bool(topic.only_new_value),
        "value": topic.value,
        "updated": topic.updated.isoformat(sep=" ", timespec="seconds") if topic.updated else None,
    }


def apply_payload(topic: Topic, payload: Dict[str, Any]) -> None:
    for field in _TOPIC_FIELDS:
        if field in payload:
            setattr(topic, field, payload[field])
    topic.updated = get_now_to_utc()


def save_topic(payload: Dict[str, Any], entity_id: Optional[int] = None) -> Tuple[Topic, Optional[str]]:
    old_object = None
    old_property = None
    topic = None

    if entity_id is not None:
        topic = Topic.query.get(entity_id)
        if topic is None:
            raise ValueError(f"Topic not found: {entity_id}")
        old_object = topic.linked_object
        old_property = topic.linked_property
        apply_payload(topic, payload)
    else:
        topic = Topic()
        apply_payload(topic, payload)
        db.session.add(topic)

    if not topic.path:
        raise ValueError("path is required")

    db.session.flush()

    linked_property = (topic.linked_property or "").strip()
    if linked_property:
        ok, err = sync_property_link(
            PLUGIN_NAME,
            topic.linked_object,
            topic.linked_property,
            old_object=old_object,
            old_property=old_property,
        )
        if not ok:
            db.session.rollback()
            raise ValueError(err or "Failed to sync property link")
    elif old_property:
        remove_property_link(PLUGIN_NAME, old_object, old_property)

    db.session.commit()
    db.session.refresh(topic)
    _subscribe_topic_path(topic.path)
    return topic, None


def _subscribe_topic_path(path: Optional[str]) -> None:
    topic_path = str(path or "").strip()
    if not topic_path:
        return
    try:
        from app.core.main.PluginsHelper import plugins
        instance = plugins.get(PLUGIN_NAME, {}).get("instance")
        if instance is not None and hasattr(instance, "subscribe_topic"):
            instance.subscribe_topic(topic_path)
    except Exception:
        pass


def delete_topic(entity_id: int) -> bool:
    topic = Topic.query.get(entity_id)
    if topic is None:
        return False
    if topic.linked_property:
        remove_property_link(PLUGIN_NAME, topic.linked_object, topic.linked_property)
    db.session.delete(topic)
    db.session.commit()
    return True
