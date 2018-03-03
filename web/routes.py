from os.path import join as jp
from os import makedirs
from flask import render_template, render_template_string, abort, Markup,\
send_from_directory, flash, redirect, g, request
from flask_misaka import markdown
from web import app
from web.forms import make_form, VotingForm
from ruamel.yaml import YAML
from threading import Lock
import secrets

# Lock on all application related stuff.
# Because this is so low-volume, we can just keep one
# and write to ONE file
apply_lock = Lock()

with apply_lock:
    # Load configs with the module
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

    # If applications aren't currently enabled, say so
    if not applyconfig['enable']:
        return render_template('content.html', title='Apply',
                               content='<h1>Apply</h1>'
                                       '<p>Applications are '
                                       'currently closed.</p>')

    # Otherwise, check if this application name is listed
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

            with apply_lock:

                try:
                    with open(jp(applyconfig['destination'], 'meta.yml')) as f:
                        submissions = yaml.load(f)
                except FileNotFoundError:
                    submissions = {}
                application_valid = True

                for submission in submissions:
                    s = submissions[submission]
                    if s['origin'] == request.remote_addr \
                            and s['active']:
                        application_valid = False
                        break

                if application_valid:
                    
                    appid = secrets.token_hex(32)
                    token = secrets.token_hex(32)
                    submission_fields = []
                    submission = {}

                    for field in form:
                        if field.flags.dynamic:
                            fieldval = {
                                    'name': field.name,
                                    'description': field.description,
                                    'value': field.data,
                                    'mask': False
                            }
                            submission_fields.append(fieldval)
                        if field.flags.mask and field.data:
                            submission_fields[-1]['mask'] = True

                    submission = {
                            'type': name,
                            'active': True,
                            'origin': request.remote_addr,
                            'token': token,
                            'responses': {}
                    }

                    submissions.update({appid: submission})

                    makedirs(applyconfig['destination'], exist_ok=True)
                    with open(jp(applyconfig['destination'], appid+'.yml'), 'w') as f:
                        yaml.dump(submission_fields, f)
                    with open(jp(applyconfig['destination'], 'meta.yml'), 'w') as f:
                        yaml.dump(submissions, f)

                    flash('Application submitted! Good luck!')
                else:
                    flash('Your IP address already has an application on file!')

            return redirect('/')

        return render_template('apply.html', form=form,
                               form_name=application['name'],
                               form_description=application['description'])
    else:
        abort(404)


@app.route('/vote/<appid>', defaults={'token': None}, methods=['GET', 'POST'])
@app.route('/vote/<appid>/<token>', methods=['GET', 'POST'])
def vote(appid, token):

    form = VotingForm()
    meta_loaded = False

    if form.validate_on_submit():
        with apply_lock:
            with open(jp(applyconfig['destination'], 'meta.yml')) as f:
                submissions = yaml.load(f)
                meta_loaded = True

            submission = submissions[appid]

            submission['responses'][request.remote_addr] = form.response.data

            with open(jp(applyconfig['destination'], 'meta.yml'), 'w') as f:
                yaml.dump(submissions, f)

        flash('Thanks for voting! To change your vote, just vote again.')
                

    with apply_lock:

        try:
            if not meta_loaded: 
                with open(jp(applyconfig['destination'], 'meta.yml')) as f:
                    submissions = yaml.load(f)
        except FileNotFoundError:
            abort(404)

        if not appid in submissions:
            abort(404)

        with open(jp(applyconfig['destination'], appid+'.yml')) as f:
            fields = yaml.load(f)

    submission = submissions[appid]
    token_valid = (token is not None) and (token == submission['token'])

    total_results = len(submission['responses'])
    yes_results = len([x for x in submission['responses'] if submission['responses'][x]])
    no_results = total_results - yes_results
    try:
        percent_yes = yes_results * 100 / total_results
        percent_no = no_results * 100 / total_results
    except ZeroDivisionError:
        percent_yes = percent_no = 50

    results = {'yes': yes_results, 'no': no_results, 'total': total_results, 
               'percent_yes': percent_yes, 'percent_no': percent_no}
    
    return render_template('vote.html', submission=fields, metadata=submission,
                           admin=token_valid, form=form, addr=request.remote_addr,
                           results=results)


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


