# Docker Commands for Dokan API

## Important: Docker Compose V2

This project uses **Docker Compose V2**, which uses `docker compose` (with a space) instead of `docker-compose` (with a hyphen).

## Prerequisites

1. **Start Docker daemon:**
   ```bash
   # On Linux (systemd)
   sudo systemctl start docker
   
   # Or if using Docker Desktop, make sure it's running
   ```

2. **Verify Docker is running:**
   ```bash
   docker ps
   ```

## Common Commands

### Build and Start Services
```bash
# Build images (no cache)
docker compose build --no-cache

# Build and start in detached mode
docker compose up -d --build

# Start services
docker compose up -d

# View logs
docker compose logs -f web
docker compose logs -f db
```

### Stop and Remove
```bash
# Stop services
docker compose down

# Stop and remove volumes (WARNING: deletes database data)
docker compose down -v
```

### Database Operations
```bash
# Run migrations
docker compose exec web python manage.py migrate

# Create superuser
docker compose exec web python manage.py createsuperuser

# Access PostgreSQL shell
docker compose exec db psql -U dokan_user -d dokan_db
```

### Other Useful Commands
```bash
# View running containers
docker compose ps

# Execute commands in container
docker compose exec web python manage.py shell
docker compose exec web python manage.py collectstatic --noinput

# Rebuild specific service
docker compose build web

# View container logs
docker compose logs web
docker compose logs db
```

## Troubleshooting

### Docker daemon not running
```bash
# Check Docker status
sudo systemctl status docker

# Start Docker
sudo systemctl start docker

# Enable Docker to start on boot
sudo systemctl enable docker
```

### Permission denied
```bash
# Add your user to docker group (logout/login required)
sudo usermod -aG docker $USER

# Or use sudo (not recommended for regular use)
sudo docker compose up
```

### Port already in use
```bash
# Check what's using the port
sudo lsof -i :8000
sudo lsof -i :5432

# Change ports in .env file
API_PORT=8001
POSTGRES_PORT=5433
```

### Clean rebuild
```bash
# Stop everything
docker compose down -v

# Remove all images
docker compose rm -f

# Rebuild from scratch
docker compose build --no-cache
docker compose up -d
```
