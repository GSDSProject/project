import uuid

from flask import request, make_response, jsonify
from flask_restx import Resource, Namespace

ns = Namespace('brainstorming', description='Brainstorming operations')


@ns.route('/')
@ns.doc()
class Brainstorming(Resource):
    def get(self):
        user_id = request.cookies.get('user_id')
        if not user_id:
            user_id = str(uuid.uuid4())
            response = make_response({'user_id': user_id})
            response.set_cookie('user_id', user_id)
        else:
            response = make_response({'user_id': user_id})
        return response


@ns.route('/db')
@ns.doc()
class CheckDB(Resource):
    def get(self):
        from home.db import db
        return jsonify(list(db.conceptnet.find({}).limit(20)))
