# Use an official Python 3.10 image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expose the Flask default port
EXPOSE 5000

# Run the app
CMD ["python", "main.py"]
