from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, IntegerField
from wtforms.validators import DataRequired

# Определение класса формы
class SettingsForm(FlaskForm):
    host = StringField('Host', validators=[DataRequired()])
    port = IntegerField('Port', validators=[DataRequired()], default=1883)
    topic = StringField('Topic', validators=[DataRequired()])
    submit = SubmitField('Submit')