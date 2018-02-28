from os.path import join as jp
from flask import render_template, render_template_string, abort, Markup
from flask_misaka import markdown
from web import app
from ruamel.yaml import YAML

yaml = YAML()
with open('config.yml') as f:
    config = yaml.load(f)


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
            content = markdown(f.read())
        return render_template('content.html', title=article, content=content)
    except OSError:
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
