# Mqtt — примеры использования

Ниже несколько сценариев “с нуля”. Во всех примерах предполагается, что:
1) osysHome уже запущен и плагин `Mqtt` доступен в админке,
2) в `Mqtt -> Settings` включена подписка `Subscribe topics`, чтобы брокер доставлял сообщения в osysHome.

## Сценарий 1: строка/булевое значение в свойство объекта

Цель: принимать значения `true/false` из MQTT и обновлять свойство `state` объекта `MQTTRelay`.

### 1) Подготовьте объект osysHome
1. Админка -> `Objects` -> создайте объект `MQTTRelay`.
2. Добавьте свойство:
   - `state` (тип `bool`)

### 2) Настройте плагин `Mqtt`
1. `Mqtt -> Settings`:
   - `Host/Port/Username/Password` (если нужно)
   - `Subscribe topics`: `home/relay/state`
2. `Mqtt -> Add topic`:
   - `Name`: `Relay state`
   - `Path`: `home/relay/state`
   - `Linked object`: `MQTTRelay`
   - `Linked property`: `state`
   - `Readonly`: выключено (чтобы поддерживать двусторонность)
   - `QOS`: 0
   - `Retain`: по необходимости
   - `Only new value`: по желанию

### 3) Входящее MQTT сообщение (тест)
Публикуйте в MQTT:
- topic: `home/relay/state`
- payload: `true`

Если ваша автоматика шлёт `1/0`, используйте payload `1` или `0`.

### 4) Проверка результата в osysHome
В автоматизации/таске используйте:

```python
# Проверка: должно стать True
state = getProperty("MQTTRelay.state")
log("MQTT state = " + str(state))
```

## Сценарий 2: двусторонние команды с `Replace list` (OPEN/CLOSED)

Цель: принимать статусы `OPEN`/`CLOSED` и хранить их как `bool open` в osysHome. При изменении `open` в osysHome плагин опубликует команду обратно в MQTT.

### 1) Подготовьте объект osysHome
1. Создайте объект `MQTTHouseDoor`.
2. Добавьте свойство:
   - `open` (тип `bool`)

### 2) Настройте плагин `Mqtt`
1. `Mqtt -> Settings`:
   - `Subscribe topics`: `home/door/status`
2. `Mqtt -> Add topic`:
   - `Name`: `Door status`
   - `Path` (вход): `home/door/status`
   - `Path write` (исходящие команды): `home/door/set`
   - `Linked object`: `MQTTHouseDoor`
   - `Linked property`: `open`
   - `Readonly`: выключено
   - `Only new value`: включено (чтобы не спамить одинаковыми командами)
   - `Replace list` (формат `FROM=TO`, пары через запятую): `OPEN=1,CLOSED=0`
   - `QOS`: 0

Важно: замены применяются в обе стороны:
1) При входе: `OPEN` -> `1` (а затем `bool` -> `True`)
2) При выходе: `True/1` -> `OPEN`

### 3) Входящее MQTT сообщение (тест)
- topic: `home/door/status`
- payload: `OPEN`

После этого в osysHome свойство `MQTTHouseDoor.open` должно стать `True`.

### 4) Отправка команды из osysHome (проверка двусторонности)
В задаче osysHome установите:

```python
setProperty("MQTTHouseDoor.open", False)
```

Ожидаемый результат: плагин опубликует в `home/door/set` payload `CLOSED`.

## Сценарий 3: JSON payload в свойство типа `dict`

Цель: принимать JSON-объект из MQTT и хранить его в свойстве `payload` типа `dict`.

### 1) Подготовьте объект osysHome
1. Создайте объект `MqttWeather`.
2. Добавьте свойство:
   - `payload` (тип `dict`)

### 2) Настройте плагин `Mqtt`
1. `Mqtt -> Settings`:
   - `Subscribe topics`: `home/weather`
2. `Mqtt -> Add topic`:
   - `Name`: `Weather`
   - `Path`: `home/weather`
   - `Linked object`: `MqttWeather`
   - `Linked property`: `payload`
   - `Readonly`: по необходимости

### 3) Входящее MQTT сообщение (JSON)

Публикуйте:
- topic: `home/weather`
- payload (JSON как текст):

```json
{
  "temp": 21.5,
  "humidity": 45,
  "unit": "C"
}
```

### 4) Проверка результата в osysHome
```python
data = getProperty("MqttWeather.payload")
log("Weather temp = " + str(data.get("temp")))
```

## REST API (для админа): быстрые проверки через `curl`

Для запросов нужен API key пользователя с ролью `admin`. В коде используются:
1) query-параметр `apikey=...`
2) заголовок `X-API-Key: ...`

### 1) Проверить статус подключения к MQTT

```bash
curl -sS -G "http://localhost/api/mqtt/status" \
  --data-urlencode "apikey=YOUR_API_KEY"
```

Ожидаемый ответ:
```json
{
  "status": "connected|connecting|disconnected|error",
  "reconnect_attempts": 0,
  "is_connected": true
}
```

### 2) Получить дерево топиков (которые настроены в osysHome)

```bash
curl -sS "http://localhost/api/mqtt/topics?apikey=YOUR_API_KEY"
```

Ответ будет JSON-объектом-деревом по сегментам `Topic.path` (leaf-узлы содержат поля записи `mqtt_topics`, включая `value` и `updated`).

## Код интеграции: python-requests (GET /status)

```python
import requests

url = "http://localhost/api/mqtt/status"
api_key = "YOUR_API_KEY"

resp = requests.get(url, params={"apikey": api_key}, timeout=10)
resp.raise_for_status()
print(resp.json())
```

