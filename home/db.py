from flask import current_app, g
from flask_pymongo import PyMongo
from werkzeug.local import LocalProxy


def get_db():
    my_db = getattr(g, '_database', None)
    if my_db is None:
        my_db = g._database = PyMongo(current_app).db
    return my_db


db = LocalProxy(get_db)
