import json
from flask import request, jsonify
from flask_restx import Namespace, Resource
from sqlalchemy import delete
from app.api.decorators import api_key_required
from app.authentication.handlers import handle_admin_required
from app.api.models import model_404, model_result
from plugins.Mqtt.models.Mqtt import Topic
from app.database import row2dict, session_scope

_api_ns = Namespace(name="MQTT", description="MQTT namespace", validate=True)

response_result = _api_ns.model("Result", model_result)
response_404 = _api_ns.model("Error", model_404)


def create_api_ns():
    return _api_ns


def build_topic_tree(topics_data):
    tree = {}
    for topic_rec in topics_data:
        parts = topic_rec.path.split('/')
        current_level = tree
        
        for i, part in enumerate(parts):
            if part == "":
                part = "/"
            if i < len(parts) - 1:  # Если это не последняя часть
                if part not in current_level:
                    current_level[part] = {"children": {}}
                current_level = current_level[part]["children"]
            else:  # Последняя часть — это листовой узел
                if part not in current_level:
                    current_level[part] = {"children": {}}
                data = row2dict(topic_rec)
                current_level[part].update(data)  # Добавляем данные
                
    return tree

@_api_ns.route("/topics", endpoint="mtqq_topics")
class GetTopics(Resource):
    @api_key_required
    @handle_admin_required
    @_api_ns.doc(security="apikey")
    @_api_ns.response(200, "List tasks", response_result)
    def get(self):
        with session_scope() as session:
            topics = session.query(Topic).all()
            topic_tree = build_topic_tree(topics)
            return jsonify(topic_tree)


