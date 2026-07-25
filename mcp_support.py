"""MCP integration helpers for Mqtt plugin."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, or_

from app.core.lib.mcp_contract import (
    build_plugin_mcp_descriptors,
    revision_from_datetime,
    revision_from_dict,
    validate_entity_payload,
)
from app.core.lib.plugin_binding import (
    validate_object_exists,
    validate_object_property_exists,
)
from app.core.main.ObjectsStorage import objects_storage

from plugins.Mqtt.models.Mqtt import Topic
from plugins.Mqtt.services import topic_service

PLUGIN_NAME = "Mqtt"
TOPICS_COLLECTION = "topics"

_TOPIC_WRITABLE_FIELDS = (
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
)

_REPLACE_LIST_PAIR_RE = re.compile(r"^[^=]+=.+$")


def _plugin_instance():
    try:
        from app.core.main.PluginsHelper import plugins
        return plugins.get(PLUGIN_NAME, {}).get("instance")
    except Exception:
        return None


def validate_object_method_exists(object_name: Optional[str], method_name: Optional[str]) -> bool:
    obj_name = str(object_name or "").strip()
    meth_name = str(method_name or "").strip()
    if not obj_name or not meth_name:
        return False
    obj = objects_storage.getObjectByName(obj_name)
    if obj is None:
        return False
    return meth_name in obj.methods


def _validate_replace_list(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    for pair in text.split(","):
        item = pair.strip()
        if not item:
            continue
        if not _REPLACE_LIST_PAIR_RE.match(item):
            return f"invalid replace_list pair: {item!r} (expected key=value)"
    return None


def _merge_topic_payload(payload: dict, entity_id=None) -> dict:
    merged = dict(payload or {})
    if entity_id in (None, ""):
        return merged
    topic = Topic.query.get(int(entity_id))
    if topic is None:
        return merged
    current = topic_service.topic_to_dict(topic)
    for field in _TOPIC_WRITABLE_FIELDS:
        if field not in merged and field in current:
            merged[field] = current[field]
    return merged


def _resolve_publish_path(topic_id=None, path: Optional[str] = None) -> Tuple[str, Optional[int]]:
    if path and str(path).strip():
        return str(path).strip(), None
    if topic_id in (None, ""):
        raise ValueError("path or topic_id is required")
    topic = Topic.query.get(int(topic_id))
    if topic is None:
        raise ValueError(f"Topic not found: {topic_id}")
    publish_path = (topic.path_write or topic.path or "").strip()
    if not publish_path:
        raise ValueError(f"Topic {topic_id} has no publish path")
    return publish_path, topic.id


def _resolve_topic_lookup(topic_id=None, path: Optional[str] = None) -> Topic:
    if topic_id not in (None, ""):
        topic = Topic.query.get(int(topic_id))
        if topic is None:
            raise ValueError(f"Topic not found: {topic_id}")
        return topic
    lookup_path = str(path or "").strip()
    if not lookup_path:
        raise ValueError("topic_id or path is required")
    topic = Topic.query.filter(Topic.path == lookup_path).order_by(Topic.id).first()
    if topic is None:
        raise ValueError(f"Topic not found for path: {lookup_path}")
    return topic


def mcp_capabilities() -> dict:
    return {
        "mcp_version": 1,
        "entities": True,
        "config_schema": True,
        "notes": [
            "Subscribe topics are configured globally in plugin config 'topic' (wildcards allowed, e.g. home/#).",
            "Entity path is also subscribed automatically when a topic is created or updated.",
            "Setting 'value' via upsert does not publish to MQTT and does not update linked properties.",
            "Use publish_message for one-off publishes; use property binding for bidirectional sync.",
            "Prefer osys_bind_device over manual upsert plus manage_property_links.",
            "Upsert without entity_id updates an existing topic with the same path (no duplicates).",
            "Check get_connection_status before changing broker config or publishing.",
            "replace_list maps MQTT payload strings to linked property values (comma-separated key=value pairs).",
            "Use replace_list when MQTT sends text but linked property type is int/float/bool "
            "(e.g. online=1,offline=0 for int; ON=1,OFF=0). Applied on inbound before setProperty "
            "and reversed on outbound publish.",
            "If setProperty fails with int()/float() conversion errors, inspect linked property type "
            "and add or fix replace_list on the topic entity.",
        ],
        "collections": [
            {
                "id": TOPICS_COLLECTION,
                "title": "MQTT Topics",
                "binding_mode": "property",
                "writable": True,
                "has_code": False,
                "list_filters": ["query", "linked_object", "has_binding"],
                "default_sort": "title asc",
                "writable_fields": list(_TOPIC_WRITABLE_FIELDS),
                "description": (
                    "MQTT topic bindings. path = subscribe/read topic; "
                    "path_write = publish topic when linked property changes. "
                    "Use replace_list to convert MQTT strings to property types."
                ),
            }
        ],
        "operations": [
            "publish_message",
            "get_topic_value",
            "get_connection_status",
            "reconnect",
            "list_subscribed_topics",
            "publish_via_binding",
        ],
        "operation_schemas": {
            "publish_message": {
                "params": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "MQTT topic path to publish to"},
                        "topic_id": {"type": "integer", "description": "Topic entity id (uses path_write or path)"},
                        "value": {"description": "Payload value to publish"},
                        "qos": {"type": "integer", "minimum": 0, "maximum": 2},
                        "retain": {"type": "boolean"},
                    },
                    "required": ["value"],
                },
            },
            "get_topic_value": {
                "params": {
                    "type": "object",
                    "properties": {
                        "topic_id": {"type": "integer"},
                        "path": {"type": "string"},
                    },
                },
            },
            "get_connection_status": {
                "params": {"type": "object", "properties": {}},
            },
            "reconnect": {
                "params": {"type": "object", "properties": {}},
            },
            "list_subscribed_topics": {
                "params": {"type": "object", "properties": {}},
            },
            "publish_via_binding": {
                "params": {
                    "type": "object",
                    "properties": {
                        "object_name": {"type": "string"},
                        "property_name": {"type": "string"},
                        "value": {"description": "Value to publish through linked topics"},
                    },
                    "required": ["object_name", "property_name", "value"],
                },
            },
        },
    }


def mcp_config_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "host": {"type": "string", "description": "MQTT broker host"},
            "port": {"type": "integer", "default": 1883},
            "protocol": {
                "type": "string",
                "enum": ["3.1", "3.1.1", "5.0"],
                "default": "3.1.1",
            },
            "topic": {
                "type": "string",
                "description": "Default subscribe topics, comma-separated (wildcards allowed)",
            },
            "login": {"type": "string"},
            "password": {"type": "string", "writeOnly": True},
            "auto_add": {
                "type": "boolean",
                "default": False,
                "description": "Auto-create topic rows for unknown incoming paths",
            },
        },
    }


def mcp_entity_schema(collection: str) -> dict:
    if collection != TOPICS_COLLECTION:
        raise ValueError(f"Unsupported collection: {collection}")
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Display name for admin UI"},
            "path": {
                "type": "string",
                "description": "Subscribe/read MQTT topic (matched on incoming messages)",
            },
            "path_write": {
                "type": "string",
                "description": "Publish topic when linked property changes; falls back to path",
            },
            "linked_object": {"type": "string", "description": "osysHome object name"},
            "linked_property": {"type": "string", "description": "Property on linked object"},
            "linked_method": {
                "type": "string",
                "description": "Method called when a message arrives on path",
            },
            "qos": {"type": "integer", "minimum": 0, "maximum": 2, "description": "MQTT QoS level"},
            "retain": {"type": "boolean", "description": "Retain flag on outbound publish"},
            "replace_list": {
                "type": "string",
                "description": (
                    "Comma-separated MQTT-to-property value map: key=value,key=value. "
                    "Inbound: MQTT payload replaces key before setProperty. "
                    "Outbound: property value maps back to MQTT key on publish. "
                    "Example: online=1,offline=0 for int property; ON=1,OFF=0 for bool/int."
                ),
            },
            "readonly": {
                "type": "boolean",
                "description": "Skip outbound publish when linked property changes",
            },
            "only_new_value": {
                "type": "boolean",
                "description": "Ignore duplicate inbound values",
            },
            "value": {
                "type": "string",
                "readOnly": True,
                "description": "Last received payload (runtime, not writable via upsert)",
            },
            "updated": {
                "type": "string",
                "readOnly": True,
                "description": "Last update timestamp (used for if_match revision)",
            },
        },
        "required": ["path"],
    }


def _parse_optional_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def mcp_list_entities(
    collection: str,
    query: str = None,
    limit: int = 100,
    linked_object: str = None,
    has_binding: bool = None,
) -> List[dict]:
    if collection != TOPICS_COLLECTION:
        raise ValueError(f"Unsupported collection: {collection}")
    q = Topic.query
    if query:
        like = f"%{query}%"
        q = q.filter(
            or_(
                Topic.title.ilike(like),
                Topic.path.ilike(like),
                Topic.linked_object.ilike(like),
                Topic.linked_property.ilike(like),
                Topic.linked_method.ilike(like),
            )
        )
    linked_obj = str(linked_object or "").strip()
    if linked_obj:
        q = q.filter(Topic.linked_object == linked_obj)
    binding_filter = _parse_optional_bool(has_binding)
    if binding_filter is True:
        q = q.filter(
            or_(
                and_(Topic.linked_property.isnot(None), Topic.linked_property != ""),
                and_(Topic.linked_method.isnot(None), Topic.linked_method != ""),
            )
        )
    elif binding_filter is False:
        q = q.filter(
            or_(Topic.linked_property.is_(None), Topic.linked_property == ""),
        ).filter(
            or_(Topic.linked_method.is_(None), Topic.linked_method == ""),
        )
    rows = q.order_by(Topic.title).limit(max(1, min(int(limit or 100), 5000))).all()
    return [topic_service.topic_to_dict(row) for row in rows]


def mcp_get_entity(collection: str, entity_id) -> dict:
    if collection != TOPICS_COLLECTION:
        raise ValueError(f"Unsupported collection: {collection}")
    topic = Topic.query.get(entity_id)
    if topic is None:
        raise ValueError(f"Topic not found: {entity_id}")
    return topic_service.topic_to_dict(topic)


def mcp_upsert_entity(collection: str, payload: dict, entity_id=None) -> dict:
    if collection != TOPICS_COLLECTION:
        raise ValueError(f"Unsupported collection: {collection}")
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    clean_payload = dict(payload)
    clean_payload.pop("value", None)
    clean_payload.pop("updated", None)
    clean_payload.pop("id", None)
    validation = mcp_validate_entity(collection, clean_payload, entity_id=entity_id)
    if not validation.get("ok"):
        raise ValueError(f"validation failed: {validation}")
    topic, _ = topic_service.save_topic(clean_payload, entity_id=entity_id)
    return topic_service.topic_to_dict(topic)


def mcp_delete_entity(collection: str, entity_id) -> bool:
    if collection != TOPICS_COLLECTION:
        raise ValueError(f"Unsupported collection: {collection}")
    return topic_service.delete_topic(int(entity_id))


def mcp_validate_entity_code(collection: str, code: str) -> dict:
    raise ValueError(f"Collection '{collection}' does not support code validation")


def mcp_run_entity_dry(collection: str, code: str, context: dict = None) -> dict:
    raise ValueError(f"Collection '{collection}' does not support dry-run code")


def mcp_invoke(operation: str, params: dict = None) -> dict:
    params = params or {}
    if operation == "publish_message":
        if "value" not in params:
            raise ValueError("value is required")
        publish_path, topic_id = _resolve_publish_path(
            topic_id=params.get("topic_id"),
            path=params.get("path"),
        )
        qos = params.get("qos", 0)
        retain = bool(params.get("retain", False))
        if topic_id is not None:
            topic = Topic.query.get(topic_id)
            if topic is not None:
                qos = params.get("qos", topic.qos if topic.qos is not None else 0)
                retain = bool(params.get("retain", topic.retain))
        instance = _plugin_instance()
        if instance is None:
            raise ValueError("Mqtt plugin not loaded")
        published = instance.mqttPublish(publish_path, params.get("value"), qos=qos, retain=retain)
        return {
            "ok": published,
            "operation": operation,
            "path": publish_path,
            "topic_id": topic_id,
            "published": published,
        }
    if operation == "get_topic_value":
        topic = _resolve_topic_lookup(topic_id=params.get("topic_id"), path=params.get("path"))
        data = topic_service.topic_to_dict(topic)
        return {
            "ok": True,
            "operation": operation,
            "topic_id": topic.id,
            "path": topic.path,
            "value": data.get("value"),
            "updated": data.get("updated"),
        }
    if operation == "get_connection_status":
        instance = _plugin_instance()
        if instance is None:
            raise ValueError("Mqtt plugin not loaded")
        is_connected = False
        client = getattr(instance, "_client", None)
        if client is not None:
            try:
                is_connected = client.is_connected()
            except Exception:
                is_connected = False
        return {
            "ok": True,
            "operation": operation,
            "status": getattr(instance, "_connection_status", "unknown"),
            "is_connected": is_connected,
            "reconnect_attempts": getattr(instance, "_reconnect_attempts", 0),
            "host": (instance.config.get("host") or "").strip(),
            "port": instance.config.get("port", 1883),
        }
    if operation == "reconnect":
        instance = _plugin_instance()
        if instance is None:
            raise ValueError("Mqtt plugin not loaded")
        instance._reconnect_attempts = 0
        connected = instance._connect_mqtt()
        return {
            "ok": connected,
            "operation": operation,
            "connected": connected,
            "status": getattr(instance, "_connection_status", "unknown"),
        }
    if operation == "list_subscribed_topics":
        instance = _plugin_instance()
        if instance is None:
            raise ValueError("Mqtt plugin not loaded")
        topic_config = (instance.config.get("topic") or "").strip()
        topics = [item.strip() for item in topic_config.split(",") if item.strip()]
        entity_paths = [
            row.path.strip()
            for row in Topic.query.filter(Topic.path.isnot(None), Topic.path != "").all()
            if row.path and row.path.strip()
        ]
        return {
            "ok": True,
            "operation": operation,
            "config_topics": topics,
            "entity_paths": sorted(set(entity_paths)),
        }
    if operation == "publish_via_binding":
        object_name = str(params.get("object_name") or "").strip()
        property_name = str(params.get("property_name") or "").strip()
        if not object_name or not property_name:
            raise ValueError("object_name and property_name are required")
        if "value" not in params:
            raise ValueError("value is required")
        instance = _plugin_instance()
        if instance is None:
            raise ValueError("Mqtt plugin not loaded")
        instance.changeLinkedProperty(object_name, property_name, params.get("value"))
        return {
            "ok": True,
            "operation": operation,
            "object_name": object_name,
            "property_name": property_name,
        }
    raise ValueError(f"Unsupported operation: {operation}")


def mcp_descriptors() -> Tuple[list, list, list]:
    return build_plugin_mcp_descriptors(PLUGIN_NAME, mcp_capabilities())


def mcp_entity_revision(collection: str, entity_id) -> str:
    if collection != TOPICS_COLLECTION:
        raise ValueError(f"Unsupported collection: {collection}")
    entity = mcp_get_entity(collection, entity_id)
    updated = revision_from_datetime(entity.get("updated"))
    if updated:
        return updated
    return revision_from_dict(
        entity,
        keys=[
            "id",
            "title",
            "path",
            "path_write",
            "linked_object",
            "linked_property",
            "linked_method",
            "qos",
            "retain",
            "readonly",
            "only_new_value",
            "value",
        ],
    )


def mcp_validate_entity(collection: str, payload: dict, entity_id=None) -> dict:
    if collection != TOPICS_COLLECTION:
        raise ValueError(f"Unsupported collection: {collection}")
    if not isinstance(payload, dict):
        return {"ok": False, "errors": [{"field": "_", "message": "payload must be an object"}]}

    merged = _merge_topic_payload(payload, entity_id=entity_id)
    schema = mcp_entity_schema(collection)
    result = validate_entity_payload(merged, schema)
    if not result.get("ok"):
        return result

    errors = list(result.get("errors") or [])
    warnings: List[dict] = []

    linked_object = str(merged.get("linked_object") or "").strip()
    linked_property = str(merged.get("linked_property") or "").strip()
    linked_method = str(merged.get("linked_method") or "").strip()

    if linked_property and not linked_object:
        errors.append({"field": "linked_object", "message": "required when linked_property is set"})
    if linked_method and not linked_object:
        errors.append({"field": "linked_object", "message": "required when linked_method is set"})

    if linked_object and not validate_object_exists(linked_object):
        errors.append({"field": "linked_object", "message": f"Object not found: {linked_object}"})

    if linked_object and linked_property:
        if not validate_object_property_exists(linked_object, linked_property):
            errors.append({
                "field": "linked_property",
                "message": f"Object property not found: {linked_object}.{linked_property}",
            })

    if linked_object and linked_method and not validate_object_method_exists(linked_object, linked_method):
        errors.append({
            "field": "linked_method",
            "message": f"Object method not found: {linked_object}.{linked_method}",
        })

    replace_error = _validate_replace_list(merged.get("replace_list"))
    if replace_error:
        errors.append({"field": "replace_list", "message": replace_error})

    qos = merged.get("qos")
    if qos is not None and (not isinstance(qos, int) or isinstance(qos, bool) or qos < 0 or qos > 2):
        errors.append({"field": "qos", "message": "must be an integer between 0 and 2"})

    path = str(merged.get("path") or "").strip()
    if path:
        try:
            exclude_id = int(entity_id) if entity_id not in (None, "") else None
            duplicate = topic_service.find_topic_by_path(path, exclude_id=exclude_id)
            if duplicate is not None:
                if entity_id in (None, ""):
                    warnings.append({
                        "field": "path",
                        "message": (
                            f"path already used by topic id={duplicate.id}; "
                            "upsert without entity_id will update that record"
                        ),
                    })
                else:
                    errors.append({
                        "field": "path",
                        "message": f"path already used by topic id={duplicate.id}",
                    })
        except RuntimeError:
            pass

    if entity_id not in (None, ""):
        try:
            topic = Topic.query.get(int(entity_id))
            if topic is None:
                errors.append({"field": "id", "message": f"topic not found: {entity_id}"})
        except RuntimeError:
            pass

    disallowed = [key for key in payload if key in ("value", "updated", "id")]
    if disallowed:
        errors.append({
            "field": disallowed[0],
            "message": "field is read-only",
        })

    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings}

    response = {"ok": True, "errors": []}
    if warnings:
        response["warnings"] = warnings
    return response
