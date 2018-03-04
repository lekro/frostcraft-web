from os.path import join as jp
from os import makedirs, urandom
from flask import render_template, render_template_string, abort, Markup,\
send_from_directory, flash, redirect, g, request
from flask_misaka import markdown
from web import app
from web.forms import make_form, VotingForm, VotingAdminForm
from web.discord import send_application
from ruamel.yaml import YAML
from threading import Lock, Thread
from datetime import datetime, timedelta
from binascii import hexlify

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
            if 'roles' in member:
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

        if article is None:
            article = 'Documentation Index'
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

                mindelta = timedelta(days=applyconfig['apply-delay'])

                for submission in submissions:
                    s = submissions[submission]
                    # Allow people to apply to different types
                    if s['type'] != name:
                        continue
                    delta = datetime.utcnow() - s['timestamp']
                    delta = timedelta(days=delta.days, seconds=delta.seconds)
                    if s['origin'] == request.remote_addr:
                        if s['active']:
                            application_valid = False
                            break
                        if delta < mindelta:
                            application_valid = False
                            break
                            flash('Wait {} before applying again!'
                                    ''.format(str(mindelta-delta)))

                if application_valid:
                    
                    appid = hexlify(os.urandom(32))
                    token = hexlify(os.urandom(32))
                    submission_fields = []
                    submission = {}

                    first_value = None

                    for field in form:
                        if field.flags.dynamic:
                            fieldval = {
                                    'name': field.name,
                                    'description': field.description,
                                    'value': field.data,
                                    'mask': False
                            }
                            submission_fields.append(fieldval)

                            if first_value is None:
                                first_value = field.data

                        if field.flags.mask and field.data:
                            submission_fields[-1]['mask'] = True

                    submission = {
                            'type': name,
                            'active': True,
                            'origin': request.remote_addr,
                            'timestamp': datetime.utcnow(),
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

                    discord_thread = Thread(target=send_application,
                                            args=(config['discord-webhook'],
                                                'http://'+config['hostname']+''
                                                '/vote/{}'.format(appid), token),
                                                kwargs={'name': first_value})
                    discord_thread.start()
                else:
                    flash('You have already applied! Ask an operator if you '
                            'believe this to be a mistake.')

            return redirect('/')

        return render_template('apply.html', form=form,
                               form_name=application['name'],
                               form_description=application['description'])
    else:
        abort(404)


@app.route('/vote/<appid>', defaults={'token': None}, methods=['GET', 'POST'])
@app.route('/vote/<appid>/<token>', methods=['GET', 'POST'])
def vote(appid, token):

    form = VotingForm(prefix='memberform')
    adminform = VotingAdminForm(prefix='adminform')
    with apply_lock:
        try:
            with open(jp(applyconfig['destination'], 'meta.yml')) as f:
                submissions = yaml.load(f)
        except FileNotFoundError:
            abort(404)

    if not appid in submissions:
        abort(404)

    submission = submissions[appid]
    token_valid = (token is not None) and (token == submission['token'])

    # When we get stuff from the VotingForm
    if form.validate_on_submit() and form.submit.data:
        
        if submission['active']:
            submission['responses'][request.remote_addr] = form.response.data

            with apply_lock:
                with open(jp(applyconfig['destination'], 'meta.yml'), 'w') as f:
                    yaml.dump(submissions, f)

            flash('Thanks for voting! To change your vote, just vote again.')
        else:
            flash('This application is closed. You can\'t vote.')

    if adminform.validate_on_submit() and token_valid and adminform.submit.data:

        submission['active'] = not submission['active']
        with apply_lock:
            with open(jp(applyconfig['destination'], 'meta.yml'), 'w') as f:
                yaml.dump(submissions, f)

    # Get the responses
    with apply_lock:

        with open(jp(applyconfig['destination'], appid+'.yml')) as f:
            fields = yaml.load(f)

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
                           results=results, adminform=adminform)


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


