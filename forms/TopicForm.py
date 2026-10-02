from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, RadioField
from wtforms.validators import DataRequired, Optional
from app.database import parse_int_id
from plugins.Mqtt.models.Mqtt import Topic
from plugins.Mqtt.services.topic_service import save_topic

class TopicForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    path = StringField('Path', validators=[DataRequired()])
    path_write = StringField('Path write', validators=[Optional()])
    linked_object = StringField('Linked object', validators=[Optional()])
    linked_property = StringField('Linked property', validators=[Optional()])
    linked_method = StringField('Linked method')
    qos = RadioField('QOS', choices=[(0, '0'), (1, '1'), (2, '2')],default=0)
    retain = BooleanField('Retain', default=False)
    replace_list = StringField('Replace list')
    readonly = BooleanField('Read only', default=False)
    only_new_value = BooleanField('Only new value',default=False)

def routeTopic(request):
    id = parse_int_id(request.args.get('topic', None))

    if id:
        item = Topic.query.get_or_404(id)  # Получаем объект из базы данных или возвращаем 404, если не найден
        form = TopicForm(obj=item)  # Передаем объект в форму для редактирования
    else:
        form = TopicForm()

    if request.method == 'POST':
        form = TopicForm(request.form)
        if form.validate_on_submit():
            payload = {
                "title": form.title.data,
                "path": form.path.data,
                "path_write": form.path_write.data,
                "linked_object": form.linked_object.data,
                "linked_property": form.linked_property.data,
                "linked_method": form.linked_method.data,
                "qos": int(form.qos.data or 0),
                "retain": bool(form.retain.data),
                "replace_list": form.replace_list.data,
                "readonly": bool(form.readonly.data),
                "only_new_value": bool(form.only_new_value.data),
            }
            entity_id = int(id) if id else None
            save_topic(payload, entity_id=entity_id)
            return ["topics.html"]

    return ['topic.html', {
            'id': id,
            'form':form,
            }]
