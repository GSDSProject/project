from flask import Flask
from flask_restx import Api, Resource, fields

# Create a Flask app object
app = Flask(__name__)

api = Api(app, version='1.0', title='Brainstorming API',
          description='API for brainstorming helper',
          )

ns = api.namespace('brainstorming', description='Brainstorming operations')


@ns.route('/')
@ns.doc(params={'query': 'The query string'})
class Brainstorming(Resource):
    def get(self):
        return {'hello': 'world'}


# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
