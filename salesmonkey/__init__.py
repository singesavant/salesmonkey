import coloredlogs

from flask import Flask
from flask_cors import CORS
from flask_marshmallow import Marshmallow
from flask_session import Session

from .utils import ResourceCache

app = Flask("salesmonkey", instance_relative_config=True)

CONFIG = {
    'SESSION_TYPE': 'redis'
}

app.config.update(CONFIG)
app.config.from_pyfile('settings.cfg')

if app.config['DEBUG']:
    coloredlogs.install(level='DEBUG')
else:
    coloredlogs.install(level='WARN')

ma = Marshmallow(app)

cache = ResourceCache()

# config={'CACHE_TYPE': 'redis',
#                                   'CACHE_REDIS_DB': app.config['FLASK_CACHE_REDIS_DB'],
#                                   'CACHE_REDIS_HOST': app.config['FLASK_CACHE_REDIS_HOST']})


Session(app)

cors = CORS(app, resources={r"/*": {"origins": "*"}},
            supports_credentials=True)

from .rest import api_v1, specs as api_specs

from .auth.manager import login_manager

from . import (
    auth,
    beers,
    shop,
    checkout,
    brewshop
)

from .erpnext import erp_client

api_specs.init_app(app)
api_v1.init_app(app)
login_manager.init_app(app)
cache.init_app(app)
