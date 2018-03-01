from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField, TextAreaField
from wtforms.validators import DataRequired


def make_form(config):

    class F(FlaskForm):
        pass

    dynamic_fields = []

    F.agree = BooleanField('I agree')
    F.submit = SubmitField('Apply!')
    for field in config['fields']:

        validators = []
        if field['required']:
            validators.append(DataRequired())

        kwargs = {'label': field['name'], 'validators': validators}

        if 'description' in field:
            kwargs.update(description=field['description'])

        if field['type'] == 'field':
            formfield = StringField(**kwargs)
        if field['type'] == 'area':
            formfield = TextAreaField(**kwargs)
        setattr(F, field['name'], formfield)
        dynamic_fields.append(field['name'])

    form = F()

    for field in form:
        if field.name in dynamic_fields:
            field.flags.dynamic = True
    return form

