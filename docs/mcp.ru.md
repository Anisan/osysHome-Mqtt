# MCP — Mqtt

Плагин управляет MQTT-топиками и их связкой с объектами osysHome. Для runtime-операций (публикация, статус) используйте `invoke`.

## Collections

| ID | binding_mode | has_code | writable_fields | list_filters |
|----|--------------|----------|-----------------|--------------|
| `topics` | `property` | no | `title`, `path`, `path_write`, `linked_*`, `qos`, `retain`, `replace_list`, `readonly`, `only_new_value` | `query`, `linked_object`, `has_binding` |

### Семантика полей

| Поле | Описание |
|------|----------|
| `path` | Топик для входящих сообщений (subscribe/read) |
| `path_write` | Топик для исходящей публикации при изменении свойства; если пуст — используется `path` |
| `replace_list` | Карта `key=value,key=value`: преобразует MQTT-строку перед записью в свойство и обратно при публикации. **Обязательно**, если тип свойства `int`/`float`/`bool`, а MQTT шлёт текст (`online`, `ON`, …) |
| `readonly` | Не публиковать в MQTT при изменении связанного свойства |
| `only_new_value` | Игнорировать повторяющиеся входящие значения |
| `value` | **read-only** — последнее полученное значение |
| `updated` | **read-only** — время последнего обновления |

### Ограничения для агентов

- Подписка на топики: глобально через `config.topic` (допустимы wildcards, напр. `home/#`) и автоматически на каждый `path` сущности.
- Запись `value` через `upsert_entity` **не публикует** в MQTT и не обновляет связанные свойства.
- Для одноразовой публикации — `publish_message`, не upsert.
- Для binding предпочитайте `osys_bind_device`.
- Перед сменой настроек брокера — `get_connection_status`.
- При ошибках `invalid literal for int()` / `float()` в логах — проверьте тип `linked_property` и задайте `replace_list` на топике.

### replace_list (для агентов)

Формат: `mqtt_value=property_value,mqtt_value=property_value`

| Направление | Поведение |
|-------------|-----------|
| **Inbound** (MQTT → свойство) | payload ищется как ключ слева, в свойство пишется значение справа |
| **Outbound** (свойство → MQTT) | значение свойства ищется справа, в MQTT публикуется ключ слева |

Типичные случаи:

| MQTT payload | Тип свойства | replace_list |
|--------------|--------------|--------------|
| `online` / `offline` | `int` | `online=1,offline=0` |
| `ON` / `OFF` | `int` или `bool` | `ON=1,OFF=0` |
| `true` / `false` (строка) | `int` | `true=1,false=0` |

Перед upsert проверяйте через `osys_get_object` тип `linked_property`. Если MQTT-значение не приводится к типу свойства — добавьте `replace_list` в том же `upsert_entity` или отдельным patch по `entity_id`.

```json
{
  "plugin": "Mqtt",
  "action": "upsert_entity",
  "args": {
    "collection": "topics",
    "entity_id": 20,
    "payload": {
      "replace_list": "online=1,offline=0"
    }
  }
}
```

## Операции (invoke)

| operation | Описание |
|-----------|----------|
| `publish_message` | Опубликовать значение в MQTT (`path` или `topic_id`, `value`, `qos?`, `retain?`) |
| `get_topic_value` | Прочитать кэшированное значение топика (`topic_id` или `path`) |
| `get_connection_status` | Статус подключения к брокеру |
| `reconnect` | Принудительное переподключение |
| `list_subscribed_topics` | Список топиков из config и entity paths |
| `publish_via_binding` | Публикация через `linked_object` + `linked_property` |

## Примеры

### Создать топик со связкой

```json
{
  "plugin": "Mqtt",
  "action": "upsert_entity",
  "args": {
    "collection": "topics",
    "payload": {
      "title": "Lamp state",
      "path": "home/lamp/state",
      "path_write": "home/lamp/set",
      "linked_object": "LivingRoomLamp",
      "linked_property": "state",
      "qos": 0,
      "readonly": false
    }
  }
}
```

### Валидация и preview изменений

```json
{
  "plugin": "Mqtt",
  "action": "validate_entity",
  "args": {
    "collection": "topics",
    "payload": {
      "path": "home/lamp/state",
      "linked_object": "LivingRoomLamp",
      "linked_property": "state"
    }
  }
}
```

```json
{
  "plugin": "Mqtt",
  "action": "diff_entity",
  "args": {
    "collection": "topics",
    "entity_id": 1,
    "payload": {
      "readonly": true
    }
  }
}
```

### One-step binding

```json
{
  "plugin": "Mqtt",
  "action": "bind_device",
  "args": {
    "collection": "topics",
    "object_name": "LivingRoomLamp",
    "property_name": "state",
    "payload": {
      "title": "Lamp state",
      "path": "home/lamp/state",
      "path_write": "home/lamp/set"
    }
  }
}
```

### Список топиков с фильтром

```json
{
  "plugin": "Mqtt",
  "action": "list_entities",
  "args": {
    "collection": "topics",
    "linked_object": "LivingRoomLamp",
    "has_binding": true
  }
}
```

### Статус подключения

```json
{
  "plugin": "Mqtt",
  "action": "invoke",
  "args": {
    "operation": "get_connection_status",
    "params": {}
  }
}
```

### Публикация сообщения

```json
{
  "plugin": "Mqtt",
  "action": "invoke",
  "args": {
    "operation": "publish_message",
    "params": {
      "topic_id": 1,
      "value": "ON"
    }
  }
}
```

### Прочитать значение топика

```json
{
  "plugin": "Mqtt",
  "action": "invoke",
  "args": {
    "operation": "get_topic_value",
    "params": {
      "path": "home/lamp/state"
    }
  }
}
```

### Проверить связку

1. `osys_get_property` → `LivingRoomLamp.state` → `linked` содержит `Mqtt`
2. `osys_write_property` на `LivingRoomLamp.state` → публикация в MQTT
3. `get_topic_value` или повторный `osys_get_property` для проверки

### Настройки брокера

`osys_get_plugin_config` / `osys_update_plugin_config` для `plugin: "Mqtt"`.

Поля: `host`, `port`, `protocol`, `topic`, `login`, `password`, `auto_add`.

### Bulk import

```json
{
  "plugin": "Mqtt",
  "action": "import_entities",
  "args": {
    "collection": "topics",
    "dry_run": true,
    "items": [
      {
        "title": "Sensor temp",
        "path": "home/sensor/temp",
        "linked_object": "TempSensor",
        "linked_property": "value"
      }
    ]
  }
}
```

### REST API (дополнительно)

- `GET /mqtt/topics` — дерево топиков
- `GET /mqtt/status` — статус подключения
- `POST /mqtt/publish` — публикация (`path` или `topic_id`, `value`, `qos?`, `retain?`)
