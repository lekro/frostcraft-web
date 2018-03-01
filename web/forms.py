from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField
from wtforms.validators import DataRequired

class ApplicationForm(FlaskForm):

    username = StringField('Minecraft username', validators=[DataRequired()])
    submit = SubmitField('Apply!')


