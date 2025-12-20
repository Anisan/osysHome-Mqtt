import datetime
import time
import paho.mqtt.client as mqtt
from flask import redirect
from sqlalchemy import or_, delete
from app.database import session_scope
from app.database import row2dict, get_now_to_utc
from app.core.main.BasePlugin import BasePlugin
from plugins.Mqtt.models.Mqtt import Topic
from plugins.Mqtt.forms.SettingForms import SettingsForm
from plugins.Mqtt.forms.TopicForm import routeTopic
from app.core.lib.object import callMethodThread, setPropertyThread, updatePropertyThread
from app.core.lib.common import addNotify, CategoryNotify
from app.api import api


class Mqtt(BasePlugin):

    def __init__(self,app):
        super().__init__(app,__name__)
        self.title = "Mqtt"
        self.version = 1
        self.description = """Mqtt protocol"""
        self.category = "Devices"
        self.actions = ['cycle','search']
        self._client = None
        self.cache_devices = {}
        self._connection_status = "disconnected"  # disconnected, connecting, connected, error
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 5  # секунд
        self._last_reconnect_time = 0

        from plugins.Mqtt.api import create_api_ns
        api_ns = create_api_ns()
        api.add_namespace(api_ns, path="/mqtt")

    def _update_connection_status(self, status, error_message=None):
        """Обновляет статус подключения и отправляет его через WebSocket"""
        self._connection_status = status
        status_data = {
            "status": status,
            "error": error_message,
            "reconnect_attempts": self._reconnect_attempts
        }
        self.sendDataToWebsocket("connectionStatus", status_data)
        self.logger.info(f"MQTT connection status: {status}" + (f" - {error_message}" if error_message else ""))

    def _connect_mqtt(self):
        """Безопасное подключение к MQTT брокеру"""
        try:
            # Проверяем наличие хоста в конфигурации
            host = self.config.get("host", "").strip()
            if not host:
                self._update_connection_status("disconnected", "Host not configured")
                return False

            # Если клиент уже существует и подключен, не переподключаемся
            if self._client is not None:
                try:
                    if self._client.is_connected():
                        return True
                    # Если не подключен, останавливаем старый клиент
                    try:
                        self._client.loop_stop()
                        self._client.disconnect()
                    except:
                        pass
                except:
                    pass

            self._update_connection_status("connecting")
            
            # Создаем новый клиент MQTT
            self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
            # Назначаем функции обратного вызова
            self._client.on_connect = self.on_connect
            self._client.on_disconnect = self.on_disconnect
            self._client.on_message = self.on_message

            # Устанавливаем учетные данные, если они есть
            login = self.config.get("login", "").strip()
            password = self.config.get("password", "").strip()
            if login and password:
                self._client.username_pw_set(login, password)

            # Получаем порт из конфигурации
            port = self.config.get("port", 1883)
            if not isinstance(port, int):
                try:
                    port = int(port)
                except:
                    port = 1883

            # Подключаемся к брокеру MQTT с таймаутом
            self._client.connect(host, port, keepalive=60)
            # Запускаем цикл обработки сообщений в отдельном потоке
            self._client.loop_start()
            
            # Даем время на подключение
            time.sleep(1)
            
            # Даем немного больше времени на подключение и проверяем статус
            time.sleep(0.5)
            try:
                if self._client.is_connected():
                    self._reconnect_attempts = 0
                    return True
                else:
                    # Проверяем еще раз через небольшую задержку
                    time.sleep(0.5)
                    if self._client.is_connected():
                        self._reconnect_attempts = 0
                        return True
                    else:
                        self._update_connection_status("error", "Connection timeout")
                        return False
            except Exception as e:
                self.logger.error(f"Error checking connection status: {e}")
                self._update_connection_status("error", f"Connection check failed: {str(e)}")
                return False

        except Exception as e:
            error_msg = f"Connection error: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self._update_connection_status("error", error_msg)
            if self._client:
                try:
                    self._client.loop_stop()
                except:
                    pass
                self._client = None
            return False

    def initialization(self):
        """Инициализация модуля MQTT с безопасным подключением"""
        try:
            self._connect_mqtt()
        except Exception as e:
            self.logger.error(f"Error during MQTT initialization: {e}", exc_info=True)
            self._update_connection_status("error", f"Initialization failed: {str(e)}")

    def admin(self, request):
        op = request.args.get('op', '')
        if op == 'delete':
            id = request.args.get('topic', '')
            with session_scope() as session:
                sql = delete(Topic).where(Topic.id == id)
                session.execute(sql)
                session.commit()
                return redirect("Mqtt")

        result = ['topics.html']
        if op == 'add' or op == 'edit':
            result = routeTopic(request)

        settings = SettingsForm()
        if request.method == 'GET':
            settings.host.data = self.config.get('host','')
            settings.port.data = self.config.get('port',1883)
            settings.topic.data = self.config.get('topic','')
            settings.login.data = self.config.get('login','')
            settings.password.data = self.config.get('password','')
            settings.auto_add.data = self.config.get('auto_add',False)
        else:
            if settings.validate_on_submit():
                self.config["host"] = settings.host.data
                self.config["port"] = settings.port.data
                self.config["topic"] = settings.topic.data
                self.config["login"] = settings.login.data
                self.config["password"] = settings.password.data
                self.config["auto_add"] = settings.auto_add.data
                self.saveConfig()
                # Переподключаемся с новыми настройками
                if self._client is not None:
                    try:
                        self._client.loop_stop()
                        self._client.disconnect()
                    except:
                        pass
                    self._client = None
                self._reconnect_attempts = 0
                self._connect_mqtt()
                return redirect("Mqtt")

        if result[0] == 'topics.html':
            topics = Topic.query.all()

            content = {
                "form": settings,
                "topics": topics,
            }
            result = ['topics.html', content]

        return self.render(result[0], result[1])

    def cyclic_task(self):
        """Циклическая задача для управления подключением и переподключением"""
        if self.event.is_set():
            # Отключаемся от брокера MQTT
            if self._client is not None:
                try:
                    self._client.loop_stop()
                    self._client.disconnect()
                except Exception as e:
                    self.logger.error(f"Error disconnecting MQTT client: {e}")
                finally:
                    self._client = None
            self._update_connection_status("disconnected")
        else:
            # Проверяем статус подключения и переподключаемся при необходимости
            is_connected = False
            if self._client is not None:
                try:
                    is_connected = self._client.is_connected()
                except:
                    is_connected = False
            
            # Используем наш флаг статуса как дополнительную проверку
            if not is_connected or self._connection_status not in ["connected", "connecting"]:
                current_time = time.time()
                # Проверяем, прошло ли достаточно времени с последней попытки переподключения
                if current_time - self._last_reconnect_time >= self._reconnect_delay:
                    if self._reconnect_attempts < self._max_reconnect_attempts:
                        self._reconnect_attempts += 1
                        self._last_reconnect_time = current_time
                        self.logger.info(f"Attempting to reconnect MQTT (attempt {self._reconnect_attempts}/{self._max_reconnect_attempts})")
                        self._connect_mqtt()
                    else:
                        # Превышено максимальное количество попыток
                        if self._connection_status != "error":
                            self._update_connection_status("error", "Max reconnect attempts reached")
            else:
                # Подключение активно, сбрасываем счетчик попыток
                if self._reconnect_attempts > 0:
                    self._reconnect_attempts = 0
            
            self.event.wait(1.0)

    def mqttPublish(self, topic, value, qos=0, retain=False):
        """Публикация сообщения в MQTT топик с проверкой подключения"""
        if self._client is None or not self._client.is_connected():
            self.logger.warning(f"Cannot publish to {topic}: MQTT client not connected")
            return False
        try:
            self.logger.debug("Pubs: %s - %s", topic, value)
            result = self._client.publish(topic, str(value), qos=qos, retain=retain)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                self.logger.error(f"Failed to publish to {topic}: error code {result.rc}")
                return False
            return True
        except Exception as e:
            self.logger.error(f"Error publishing to {topic}: {e}", exc_info=True)
            return False

    def changeLinkedProperty(self, obj, prop, val):
        try:
            with session_scope() as session:
                properties = session.query(Topic).filter(Topic.linked_object == obj, Topic.linked_property == prop).all()
                if len(properties) == 0:
                    from app.core.lib.object import removeLinkFromObject
                    removeLinkFromObject(obj, prop, "Mqtt")
                    return
                for property in properties:
                    new_value = val

                    if property.readonly:
                        continue

                    if property.replace_list:
                        replaceList = self.parseReplaceValue(property.replace_list)
                        new_value = replaceList[str(val)]

                    # send to mqtt
                    topic = property.path
                    if property.path_write:
                        topic = property.path_write
                    self.mqttPublish(topic, new_value, property.qos, property.retain)
        except Exception as e:
            self.logger.error("Error processing linked property %s.%s=%s: %s", obj, prop, val, e)


    # Функция обратного вызова для подключения к брокеру MQTT
    def on_connect(self, client, userdata, flags, rc):
        """Обработчик успешного подключения к MQTT брокеру"""
        if rc == 0:
            self.logger.info("Connected to MQTT broker successfully")
            self._reconnect_attempts = 0
            self._update_connection_status("connected")
            
            # Подписываемся на топики
            topic_config = self.config.get("topic", "").strip()
            if topic_config:
                topics = [t.strip() for t in topic_config.split(',') if t.strip()]
                for topic in topics:
                    try:
                        result = self._client.subscribe(topic)
                        if result[0] == mqtt.MQTT_ERR_SUCCESS:
                            self.logger.info(f"Subscribed to topic: {topic}")
                        else:
                            self.logger.error(f"Failed to subscribe to {topic}: error code {result[0]}")
                    except Exception as e:
                        self.logger.error(f"Error subscribing to {topic}: {e}")
        else:
            error_messages = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorised"
            }
            error_msg = error_messages.get(rc, f"Connection failed with code {rc}")
            self.logger.error(f"MQTT connection failed: {error_msg}")
            self._update_connection_status("error", error_msg)

    def on_disconnect(self, client, userdata, rc):
        """Обработчик отключения от MQTT брокера"""
        if rc == 0:
            self.logger.info("Disconnected gracefully.")
            self._update_connection_status("disconnected")
        else:
            # Неожиданное отключение - будет попытка переподключения
            disconnect_messages = {
                1: "Client requested disconnection",
                2: "Broker disconnected the client unexpectedly",
                3: "Client exceeded timeout for inactivity",
                4: "Broker closed the connection"
            }
            msg = disconnect_messages.get(rc, f"Unexpected disconnection with code: {rc}")
            self.logger.warning(f"MQTT {msg}")
            
            # Отправляем уведомление только для неожиданных отключений
            if rc != 0:
                addNotify("Disconnect MQTT", msg, CategoryNotify.Error, self.name)
            
            self._update_connection_status("disconnected", msg)
            
            # Сбрасываем счетчик попыток для новой серии переподключений
            self._reconnect_attempts = 0

    # Функция обратного вызова для получения сообщений
    def on_message(self,client, userdata, msg):
        self.logger.debug("Subs: %s - %s",msg.topic, str(msg.payload))
        try:
            payload = msg.payload
            if '/set' in msg.topic:
                return
            if not payload:
                return False
            self.processMessage(msg.topic, payload)
        except Exception as e:
            self.logger.error("Error processing message: %s", e, exc_info=True)

    def processMessage(self, path, payload):
        with session_scope() as session:
            properties = session.query(Topic).filter(Topic.path == path).all()
            if not properties:
                if self.config.get('auto_add',False):
                    item = Topic()
                    item.path = path
                    item.title = path
                    session.add(item)
                    session.commit()
                    properties.append(item)
                else:
                    return
            for property in properties:
                value = None
                try:
                    value = payload.decode('utf-8')
                except UnicodeDecodeError:
                    property.value = "Binary data not saveв"
                    property.updated = get_now_to_utc()
                    session.commit()
                    self.sendDataToWebsocket("updateTopic",row2dict(property))

                    if property.linked_object and property.linked_method:
                        callMethodThread(property.linked_object + '.' + property.linked_method, {'VALUE': payload, 'NEW_VALUE': payload, 'TITLE': property.title}, self.name)
                        return

                if property.only_new_value and property.value == value:
                    continue
                old_value = property.value
                if property.replace_list:
                    replaceList = self.parseReplaceName(property.replace_list)
                    value = replaceList[value]
                property.value = value
                property.updated = get_now_to_utc()
                session.commit()

                self.sendDataToWebsocket("updateTopic",row2dict(property))

                if property.linked_object:
                    if property.linked_method:
                        callMethodThread(property.linked_object + '.' + property.linked_method, {'VALUE': value, 'NEW_VALUE': value, 'OLD_VALUE': old_value, 'TITLE': property.title}, self.name)
                    if property.linked_property:
                        if property.only_new_value:
                            updatePropertyThread(property.linked_object + '.' + property.linked_property, value, self.name)
                        else:
                            setPropertyThread(property.linked_object + '.' + property.linked_property, value, self.name)

    def parseReplaceName(self, s):
        pairs = s.split(',')
        # Создаем пустой словарь, в который будем добавлять элементы
        result = {}
        # Итерируемся по парам ключ-значение
        for pair in pairs:
            # Разделяем каждую пару по знаку "="
            key, value = pair.split('=')
            # Добавляем пару ключ-значение в словарь
            result[key] = value  # Преобразуем значение в целое число
        return result

    def parseReplaceValue(self, s):
        pairs = s.split(',')
        # Создаем пустой словарь, в который будем добавлять элементы
        result = {}
        # Итерируемся по парам ключ-значение
        for pair in pairs:
            # Разделяем каждую пару по знаку "="
            key, value = pair.split('=')
            # Добавляем пару ключ-значение в словарь
            result[value] = key  # Преобразуем значение в целое число
        return result

    def search(self, query: str) -> str:
        res = []
        topics = Topic.query.filter(or_(Topic.title.contains(query),Topic.path.contains(query),Topic.linked_object.contains(query),Topic.linked_property.contains(query),Topic.linked_method.contains(query))).all()
        for topic in topics:
            res.append({"url":f'Mqtt?op=edit&topic={topic.id}', "title":f'{topic.title} ({topic.path})', "tags":[{"name":"Mqtt","color":"warning"}]})
        return res
    
    def changeObject(self, event, object_name, property_name, method_name, new_value):
        with session_scope() as session:
            topics = session.query(Topic).filter(Topic.linked_object == object_name).all()
            for topic in topics:
                if new_value is None:
                    topic.linked_object = None
                    topic.linked_property = None
                    topic.linked_method = None
                elif property_name is None and method_name is None:
                    topic.linked_object = new_value
                elif property_name:
                    topic.linked_property = new_value
                elif method_name:
                    topic.linked_method = new_value

            session.commit()
