from flask import Flask
from flask_restx import Api
from dotenv import load_dotenv

from home.views.main import home
from home.views.word import similarWord

import os

api = Api(
    version='1.0',
    title='brainstorming_helper',
    prefix='/',
    description='brainstorming'
)


def create_app():
    # Create a Flask home object
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY')
    api.init_app(app)
    api.add_namespace(ns=home.ns)
    api.add_namespace(ns=similarWord.ns)
    return app
