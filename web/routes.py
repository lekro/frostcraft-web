from os.path import join as jp
from flask import render_template, render_template_string, abort, Markup,\
send_from_directory, flash, redirect, g
from flask_misaka import markdown
from web import app
from web.forms import make_form
from ruamel.yaml import YAML

yaml = YAML()
with open('config.yml') as f:
    config = yaml.load(f)
with open('applications.yml') as f:
    applyconfig = yaml.load(f)

# Enable application in the top level menu?
applications_enabled = None
if applyconfig['enable']:
    for a in applyconfig['applications']:
        if applyconfig['applications'][a]['enable']:
            applications_enabled = True
            break
if applications_enabled is None:
    applications_enabled = False


@app.before_request
def check_applications_enabled():
    g.applications_enabled = applications_enabled
    # setattr(g, 'applications_enabled', applications_enabled)


@app.route('/')
@app.route('/index')
def index():
    try:
        with open(jp(config['markdown-dir'], 'home.md')) as f:
            content = markdown(f.read())
            content = render_template_string(content,
                                             discord=Markup(config['discord-url']),
                                             patreon=Markup(config['patreon-url']),
                                             html=True)
        return render_template('content.html', title='Home', content=content)
    except OSError:
        abort(404)


@app.route('/members')
def members():

    try:
        with open('members.yml') as f:
            member_info = yaml.load(f)
        members = member_info['members']
        roles = member_info['roles']

        for member in members:
            member.roles = [{'class': 'role_'+role, 
                             'name': roles[role]['name']} for role in member['roles']]

    except OSError:
        members = None
        roles = None

    return render_template('members.html', title='Members', members=members, roles=roles)


@app.route('/docs', defaults={'article': None}) 
@app.route('/docs/<article>')
def docs(article):
    if article is None:
        article_path = jp(config['markdown-dir'], 'docs.md')
    else:
        article_path = jp(config['docs-dir'], article+'.md')

    try:
        with open(article_path) as f:
            content = markdown(f.read(), fenced_code=True)
        return render_template('content.html', title=article, content=content)
    except OSError:
        abort(404)


@app.route('/apply')
@app.route('/apply/')
def applylist():

    if not applyconfig['enable']:
        return render_template('content.html', title='Apply',
                               content='<h1>Apply</h1>'
                                       '<p>Applications are '
                                       'currently closed.</p>')
    
    else:
        return render_template('applylist.html', apps=applyconfig['applications'])


@app.route('/apply/<name>', methods=['GET', 'POST'])
def apply(name):

    if not applyconfig['enable']:
        return render_template('content.html', title='Apply',
                               content='<h1>Apply</h1>'
                                       '<p>Applications are '
                                       'currently closed.</p>')
    elif name in applyconfig['applications']:

        application = applyconfig['applications'][name]
        if not application['enable']:
            return render_template('content.html', 
                                   title=application['name']+' Application',
                                   content='<h1>Apply</h1>'
                                           '<p>This application is '
                                           'currently closed.</p>')

        form = make_form(application)

        if form.validate_on_submit():
            flash('Application submitted! Good luck!')
            return redirect('/')

        return render_template('apply.html', form=form,
                               form_name=application['name'],
                               form_description=application['description'])
    else:
        abort(404)


@app.errorhandler(404)
def not_found(error):

    try:
        # Try and find a custom 404 page
        with open(jp(config['markdown-dir'], '404.md')) as f:
            content = markdown(f.read())
            return render_template('content.html', title='404', content=content), 404
    except OSError:
        # If we don't find one use this default ugly one
        return render_template('content.html', title='404', 
                               content='<h1>404 Not Found</h1>'), 404


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(jp(app.root_path, 'static'),
                               'favicon.ico',
                               mimetype='image/vnd.microsoft.icon')


