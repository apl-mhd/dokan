# Docker Setup for Dokan API

This guide explains how to run the Dokan API using Docker with PostgreSQL.

## Prerequisites

- Docker (version 20.10 or higher)
- Docker Compose (version 2.0 or higher)

## Quick Start

1. **Clone the repository and navigate to the API directory:**
   ```bash
   cd dokan-api
   ```

2. **Create a `.env` file (optional, defaults are provided):**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` file with your preferred settings.

3. **Build and start the containers:**
   ```bash
   docker-compose up -d --build
   ```

4. **Create a superuser (optional):**
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

5. **Access the API:**
   - API: http://localhost:8000
   - Admin: http://localhost:8000/admin
   - API Docs: http://localhost:8000/swagger/

## Docker Commands

### Start services
```bash
docker-compose up -d
```

### Stop services
```bash
docker-compose down
```

### View logs
```bash
docker-compose logs -f web
docker-compose logs -f db
```

### Run migrations
```bash
docker-compose exec web python manage.py migrate
```

### Create superuser
```bash
docker-compose exec web python manage.py createsuperuser
```

### Collect static files
```bash
docker-compose exec web python manage.py collectstatic --noinput
```

### Access Django shell
```bash
docker-compose exec web python manage.py shell
```

### Access PostgreSQL shell
```bash
docker-compose exec db psql -U dokan_user -d dokan_db
```

### Rebuild containers
```bash
docker-compose up -d --build
```

### Remove all data (including database)
```bash
docker-compose down -v
```

## Environment Variables

Key environment variables (can be set in `.env` file or docker-compose.yml):

- `POSTGRES_DB`: Database name (default: dokan_db)
- `POSTGRES_USER`: Database user (default: dokan_user)
- `POSTGRES_PASSWORD`: Database password (default: dokan_password)
- `POSTGRES_PORT`: PostgreSQL port (default: 5432)
- `API_PORT`: API port (default: 8000)
- `DEBUG`: Debug mode (default: True)
- `SECRET_KEY`: Django secret key
- `DJANGO_SETTINGS_MODULE`: Settings module (default: dokan.settings.dev)

## Database

The PostgreSQL database is automatically created when the container starts. Data is persisted in a Docker volume named `postgres_data`.

To backup the database:
```bash
docker-compose exec db pg_dump -U dokan_user dokan_db > backup.sql
```

To restore the database:
```bash
docker-compose exec -T db psql -U dokan_user dokan_db < backup.sql
```

## Troubleshooting

### Database connection issues
- Ensure the `db` service is healthy before the `web` service starts
- Check database credentials in `.env` file
- Verify network connectivity: `docker-compose exec web ping db`

### Port conflicts
- Change `API_PORT` in `.env` if port 8000 is already in use
- Change `POSTGRES_PORT` in `.env` if port 5432 is already in use

### Permission issues
- Ensure Docker has proper permissions
- Check volume mounts in docker-compose.yml

### Reset everything
```bash
docker-compose down -v
docker-compose up -d --build
```

## Gunicorn Configuration

The application uses Gunicorn as the WSGI server. Configuration is managed through:

1. **gunicorn_config.py**: Main configuration file with all settings
2. **Environment variables**: Can override default settings in `.env`

### Gunicorn Settings

Key environment variables (in `.env`):
- `GUNICORN_WORKERS`: Number of worker processes (default: 4)
- `GUNICORN_WORKER_CLASS`: Worker class type (default: sync)
- `GUNICORN_TIMEOUT`: Worker timeout in seconds (default: 30)
- `GUNICORN_LOG_LEVEL`: Logging level (default: info)
- `GUNICORN_MAX_REQUESTS`: Max requests per worker before restart (default: 1000)

### Worker Classes

- `sync`: Synchronous workers (default, good for most cases)
- `gevent`: Async workers using gevent (requires gevent in requirements.txt)
- `uvicorn.workers.UvicornWorker`: For async support (requires uvicorn)

To use async workers, update `.env`:
```bash
GUNICORN_WORKER_CLASS=gevent
```

And add to requirements.txt:
```
gevent==23.9.1
```

## Production Deployment

For production:

1. Set `DEBUG=False` in `.env`
2. Set `DJANGO_SETTINGS_MODULE=dokan.settings.prod`
3. Use a strong `SECRET_KEY`
4. Configure proper `ALLOWED_HOSTS`
5. Set up SSL/TLS certificates
6. Adjust `GUNICORN_WORKERS` based on your server resources (recommended: CPU cores * 2 + 1)
7. Consider using a reverse proxy (nginx) in front of Gunicorn

The application already uses Gunicorn by default. No additional configuration needed!
