# Dockerfile

# Use a lean official Python image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy requirements file first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application source code
# This assumes your simulation code is in a 'src' folder
COPY . .
COPY schemas/ ./schemas

# Set the command to run the Gunicorn server
# This is a production-grade web server for your Flask app
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "900", "--workers", "1", "api:app"]