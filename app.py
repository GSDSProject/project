from flask import Flask

# Create a Flask app object
app = Flask(__name__)


# Define a route for the root URL
@app.route('/')
def hello_world():
    return 'Hello, World!'


# Define a route for /name/<name>
@app.route('/name/<name>')
def hello_name(name):
    return f'Hello, {name}!'


# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
