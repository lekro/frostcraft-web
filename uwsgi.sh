#!/bin/sh

cd /var/www/flask
. venv/bin/activate
uwsgi uwsgi.ini
