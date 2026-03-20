# REST API для админки: `Mqtt`

Плагин `Mqtt` добавляет REST-эндпоинты в namespace `MQTT` с префиксом `/api/mqtt/...`.

Важно: доступ к эндпоинтам защищён и требует:
1) API key пользователя (query `apikey` или заголовок `X-API-Key`)
2) роль `admin` (декоратор `handle_admin_required`)

## Аутентификация

Поддерживается один из вариантов:
- query-параметр: `?apikey=YOUR_API_KEY`
- заголовок HTTP: `X-API-Key: YOUR_API_KEY`

При отсутствии/некорректности ключа запрос завершается ошибкой с кодом `401`.

Если ключ верный, но роль пользователя не `admin`, запрос завершается ошибкой с кодом `403`.

Нужно уточнить: где именно в вашей сборке osysHome взять API key и как выдаётся роль `admin`.

## Endpoints

### GET `/api/mqtt/status`
Получить статус подключения MQTT (включая количество попыток переподключения).

Ответ (JSON):
```json
{
  "status": "connected|connecting|disconnected|error",
  "reconnect_attempts": 0,
  "is_connected": true
}
```

Если экземпляр плагина не найден, возвращается:
```json
{
  "status": "error",
  "message": "MQTT plugin not found"
}
```
и HTTP `404`.

### GET `/api/mqtt/topics`
Получить дерево MQTT-топиков, доступное в интерфейсе модуля `Mqtt`.

Ответ: JSON-объект-дерево по сегментам `Topic.path`.

Листовые узлы содержат поля записи из таблицы `mqtt_topics` (включая `value` и `updated`).

Важно: структура ответов формируется функцией `build_topic_tree(...)` и зависит от количества сегментов в `Topic.path`.

Пример фрагмента ответа (упрощённо):
```json
{
  "home": {
    "children": {
      "relay": {
        "children": {
          "state": {
            "id": 123,
            "title": "Relay state",
            "path": "home/relay/state",
            "value": "true",
            "updated": "..."
          }
        }
      }
    }
  }
}
```

## Примеры `curl`

### 1) Статус MQTT
```bash
curl -sS -G "http://localhost/api/mqtt/status" \
  --data-urlencode "apikey=YOUR_API_KEY"
```

### 2) Топики
```bash
curl -sS "http://localhost/api/mqtt/topics" \
  -H "X-API-Key: YOUR_API_KEY"
```

