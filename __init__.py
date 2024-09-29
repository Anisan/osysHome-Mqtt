import datetime
import paho.mqtt.client as mqtt
from flask import redirect
from sqlalchemy import or_, delete
from app.database import session_scope
from app.core.main.BasePlugin import BasePlugin
from plugins.Mqtt.models.Mqtt import Topic
from plugins.Mqtt.forms.SettingForms import SettingsForm
from plugins.Mqtt.forms.TopicForm import routeTopic
from app.core.lib.object import callMethodThread, setPropertyThread, updatePropertyThread
from app.core.lib.common import addNotify, CategoryNotify


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

    def initialization(self):
        # Создаем клиент MQTT
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        # Назначаем функции обратного вызова
        self._client.on_connect = self.on_connect
        self._client.on_disconnect = self.on_disconnect
        self._client.on_message = self.on_message

        if "host" in self.config:
            # Подключаемся к брокеру MQTT
            self._client.connect(self.config.get("host",""), 1883, 0)
            # Запускаем цикл обработки сообщений в отдельном потоке
            self._client.loop_start()

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
        else:
            if settings.validate_on_submit():
                self.config["host"] = settings.host.data
                self.config["port"] = settings.port.data
                self.config["topic"] = settings.topic.data
                self.saveConfig()
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
        if self.event.is_set():
            # Отключаемся от брокера MQTT
            self._client.disconnect()
            # Останавливаем цикл обработки сообщений
            self._client.loop_stop()
            self._client = None
        else:
            self.event.wait(1.0)

    def mqttPublish(self, topic, value, qos=0, retain=False):
        self.logger.info("Publish: %s - %s",topic,value)
        self._client.publish(topic, str(value), qos=qos, retain=retain)

    def changeLinkedProperty(self, obj, prop, val):
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

    # Функция обратного вызова для подключения к брокеру MQTT
    def on_connect(self,client, userdata, flags, rc):
        self.logger.info("Connected with result code " + str(rc))
        # Подписываемся на топик
        if self.config["topic"]:
            topics = self.config["topic"].split(',')
            for topic in topics:
                self._client.subscribe(topic)

    def on_disconnect(self, client, userdata, rc):
        addNotify("Disconnect MQTT",str(rc),CategoryNotify.Error,self.name)
        if rc == 0:
            self.logger.info("Disconnected gracefully.")
        elif rc == 1:
            self.logger.info("Client requested disconnection.")
        elif rc == 2:
            self.logger.info("Broker disconnected the client unexpectedly.")
        elif rc == 3:
            self.logger.info("Client exceeded timeout for inactivity.")
        elif rc == 4:
            self.logger.info("Broker closed the connection.")
        else:
            self.logger.warning("Unexpected disconnection with code: %s", rc)

    # Функция обратного вызова для получения сообщений
    def on_message(self,client, userdata, msg):
        # self.logger.debug(msg.topic + " " + str(msg.payload))
        payload = msg.payload.decode('utf-8')

        if '/set' in msg.topic:
            return

        if not payload:
            return False

        self.processMessage(msg.topic, payload)

    def processMessage(self, path, value):
        self.logger.debug(f'Topic {path} = {value}')
        with session_scope() as session:
            properties = session.query(Topic).filter(Topic.path == path).all()
            if not properties:
                return
            for property in properties:
                if property.only_new_value and property.value == value:
                    continue
                old_value = property.value
                if property.replace_list:
                    replaceList = self.parseReplaceName(property.replace_list)
                    value = replaceList[value]
                property.value = value
                property.updated = datetime.datetime.now()
                session.commit()

                if property.linked_object:
                    if property.linked_method:
                        callMethodThread(property.linked_object + '.' + property.linked_method, {'VALUE': value, 'NEW_VALUE': value, 'OLD_VALUE': old_value, 'TITLE': property.title},self.name)
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
