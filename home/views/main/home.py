from flask import Blueprint
from flask_restx import Resource, Api, Namespace

ns = Namespace('brainstorming', description='Brainstorming operations')

@ns.route('/')
@ns.doc()
class Brainstorming(Resource):
    def get(self):
        return {'hello': 'world'}
