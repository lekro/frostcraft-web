from flask import render_template
from web import app
from ruamel.yaml import YAML

yaml = YAML()

@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', title='Home')

@app.route('/members')
def members():

    try:
        with open('members.yml') as f:
            member_info = yaml.load(f)
        members = member_info['members']
        roles = member_info['roles']

        for member in members:
            member.roles = [{'class': 'role_'+role, 'name': roles[role]['name']} for role in member['roles']]

    except OSError:
        members = None
        roles = None

    return render_template('members.html', title='Members', members=members, roles=roles)

@app.route('/docs', defaults={'article': ''}) 
@app.route('/docs/<article>')
def docs(article):
    return article

