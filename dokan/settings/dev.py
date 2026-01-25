from .base import *
import os

DEBUG = True

# Database configuration - use PostgreSQL if environment variables are set, otherwise SQLite
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DATABASE_NAME', 'dokan_db'),
        'USER': os.getenv('DATABASE_USER', 'dokan_user'),
        'PASSWORD': os.getenv('DATABASE_PASSWORD', 'dokan_password'),
        'HOST': os.getenv('DATABASE_HOST', 'db'),
        'PORT': os.getenv('DATABASE_PORT', '5432'),
    }
}

# Fallback to SQLite if DATABASE_HOST is not set (for local development without Docker)
if not os.getenv('DATABASE_HOST') or os.getenv('DATABASE_HOST') == 'localhost':
    try:
        import psycopg2
    except ImportError:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }

ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True

# Static files
STATIC_ROOT = '/app/staticfiles'
MEDIA_ROOT = '/app/media'
STATIC_URL = '/static/'
MEDIA_URL = '/media/'