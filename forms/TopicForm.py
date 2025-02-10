from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, RadioField
from wtforms.validators import DataRequired, Optional
from app.database import db
from plugins.Mqtt.models.Mqtt import Topic

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
    id = request.args.get('topic', None)

    if id:
        item = Topic.query.get_or_404(id)  # Получаем объект из базы данных или возвращаем 404, если не найден
        form = TopicForm(obj=item)  # Передаем объект в форму для редактирования
    else:
        form = TopicForm()

    from app.core.lib.object import setLinkToObject, removeLinkFromObject

    if request.method == 'POST':
        form = TopicForm(request.form)
        if form.validate_on_submit():
            if id:
                oldLinkedObject = item.linked_object
                oldLinkedProperty = item.linked_property
                form.populate_obj(item)  # Обновляем значения объекта данными из формы
                newLinkedObject = item.linked_object
                newLinkedProperty = item.linked_property
                if oldLinkedObject != newLinkedObject or oldLinkedProperty != newLinkedProperty:
                    if oldLinkedProperty != "":
                        removeLinkFromObject(oldLinkedObject,oldLinkedProperty,"Mqtt")
                    if newLinkedProperty != "":
                        setLinkToObject(newLinkedObject,newLinkedProperty,"Mqtt")
            else:
                item = Topic()
                form.populate_obj(item)
                db.session.add(item)
                if item.linked_property:
                    setLinkToObject(item.linked_object,item.linked_property,"Mqtt")
            db.session.commit()  # Сохраняем изменения в базе данных
            return ["topics.html"]  # Перенаправляем на другую страницу после успешного редактирования

    return ['topic.html', {
            'id': id,
            'form':form,
            }]
