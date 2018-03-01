from flask import Flask
from ruamel.yaml import YAML

app = Flask(__name__)
yaml = YAML()

with open('config.yml') as f:
    flask_config = yaml.load(f)['flask']
    app.config.update(**flask_config)

from web import routes
