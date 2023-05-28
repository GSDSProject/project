from home import create_app

app = create_app()

# Run the Flask home
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
