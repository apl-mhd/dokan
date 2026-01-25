# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# Install system dependencies (WeasyPrint + Django)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build essentials
    gcc \
    python3-dev \
    build-essential \
    libffi-dev \
    # PostgreSQL client & headers
    postgresql-client \
    libpq-dev \
    # Pillow dependencies
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7 \
    libtiff5-dev \
    # WeasyPrint dependencies
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libgobject-2.0-0 \
    libglib2.0-0 \
    shared-mime-info \
    fonts-liberation \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app/

# Create static and media directories
RUN mkdir -p /app/staticfiles /app/media

# Expose port
EXPOSE 8000

# Default command for production
CMD ["gunicorn", "dokan.wsgi:application", "--config", "gunicorn_config.py"]
