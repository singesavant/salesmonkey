import coloredlogs

from flask import Flask
from flask_cors import CORS
from flask_marshmallow import Marshmallow
from flask_session import Session

coloredlogs.install(level='DEBUG')

app = Flask("salesmonkey", instance_relative_config=True)

CONFIG = {
    'SESSION_TYPE': 'redis'
}
app.config.update(CONFIG)
app.config.from_pyfile('settings.cfg')


ma = Marshmallow(app)

Session(app)

cors = CORS(app, resources={r"/*": {"origins": "*"}},
            supports_credentials=True)

from .rest import api_v1, specs as api_specs
from . import preorders
from .erpnext import erp_client

api_specs.init_app(app)
api_v1.init_app(app)
