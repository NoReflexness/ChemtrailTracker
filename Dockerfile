FROM python:3.12-slim

WORKDIR /app

# Install build dependencies for PyArrow and other packages
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libpng-dev \
    libjpeg-dev \
    zlib1g-dev \
    libopenblas-dev \
    liblapack-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create uploads directory
RUN mkdir -p /app/uploads

# Expose port
EXPOSE 5000

# Environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=development

# Run Flask
#CMD ["python", "-m", "flask", "run", "--host=0.0.0.0"]
# Run the Flask app
RUN pip install debugpy
CMD ["python", "-m", "debugpy", "--listen", "0.0.0.0:5678", "-m", "flask", "run", "--host=0.0.0.0"]