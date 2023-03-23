# Use the official Anaconda image as a parent image
FROM continuumio/anaconda3

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Set the environment variable for Flask
ENV FLASK_APP=app.py

# Expose port 8000 for the Gunicorn server
EXPOSE 8000

# Start the Gunicorn server with 4 worker processes
CMD ["gunicorn", "--workers=4", "--bind=0.0.0.0:8000", "app:app"]