from flask_wtf import FlaskForm, RecaptchaField
from wtforms import StringField, BooleanField, SubmitField, TextAreaField,\
        IntegerField, RadioField
from wtforms.validators import DataRequired


class VotingForm(FlaskForm):

    response = BooleanField('I would like to vote FOR this applicant.')
    submit = SubmitField('Vote!')


class VotingAdminForm(FlaskForm):

    submit = SubmitField('Activate/deactivate voting')


def make_form(config, use_recaptcha=True):

    class F(FlaskForm):
        pass

    dynamic_fields = []
    primary_field = None

    if use_recaptcha:
        F.recaptcha = RecaptchaField()
    else:
        F.recaptcha = BooleanField('captcha placeholder')

    F.agree = BooleanField('I am 13 years of age or older',
                           validators=[DataRequired(message='You must '
                               'be 13 years of age or older to apply.')])
    F.submit = SubmitField('Apply!')
    for field in config['fields']:

        validators = []
        if field['required']:
            validators.append(DataRequired())

        kwargs = {'label': field['name'], 'validators': validators}

        if 'description' in field:
            kwargs.update(description=field['description'])
        if 'primary' in field and field['primary']:
            primary_field = field['name']

        if field['type'] == 'field':
            formfield = StringField(**kwargs)
        if field['type'] == 'area':
            formfield = TextAreaField(**kwargs)
        if field['type'] == 'integer':
            formfield = IntegerField(**kwargs)
        if field['type'] == 'options':
            choices = []
            for choice in field['choices']:
                if type(choice) == str:
                    choices.append((choice, choice))
                else:
                    choices.append(tuple(choice))

            formfield = RadioField(**kwargs, choices=choices)

        setattr(F, field['name'], formfield)
        dynamic_fields.append(field['name'])

        # Add maskable checkbox
        if 'maskable' in field and field['maskable']:
            if 'mask-label' in config:
                label = config['mask-label']
            else:
                label = 'Mask this field'
            formfield = BooleanField(label)
            setattr(F, field['name'] + '_mask', formfield)

    form = F()

    for field in form:
        if field.name in dynamic_fields:
            field.flags.dynamic = True
        if field.name == primary_field:
            field.flags.primary = True
        if '_mask' in field.name:
            field.flags.mask = True
    return form

