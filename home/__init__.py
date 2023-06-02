import os

from flask import Flask
from flask_cors import CORS
from flask_restx import Api

from home.views.main import home
from home.views.word import similarWord_ts

api = Api(
    version='1.0',
    title='brainstorming_helper',
    prefix='/',
    description='brainstorming'
)


def create_app():
    # Create a Flask home object
    app = Flask(__name__)
    app.config['MONGO_URI'] = os.environ.get('MONGO_HOST')
    app.secret_key = os.environ.get('SECRET_KEY')
    api.init_app(app)
    CORS(app, supports_credentials=True)
    api.add_namespace(ns=home.ns)
    api.add_namespace(ns=similarWord_ts.ns)
    return app
