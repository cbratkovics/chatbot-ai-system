# Docker Deployment Guide

## Quick Start

### Development Environment

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Production Environment

```bash
# Create secrets
mkdir -p secrets
echo "your-openai-key" > secrets/openai_key.txt
echo "your-anthropic-key" > secrets/anthropic_key.txt
echo "strong-db-password" > secrets/db_password.txt
echo "random-secret-key" > secrets/secret_key.txt
echo "grafana-admin-password" > secrets/grafana_password.txt

# Start production stack
docker-compose -f docker-compose.prod.yml up -d

# Scale services
docker-compose -f docker-compose.prod.yml up -d --scale backend=3 --scale frontend=2
```

## Common Docker Commands

### Building Images

```bash
# Build all services
docker-compose build

# Build specific service
docker-compose build backend

# Build with no cache
docker-compose build --no-cache

# Build for production
docker-compose -f docker-compose.prod.yml build
```

### Managing Containers

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose stop

# Restart services
docker-compose restart

# Remove containers and networks
docker-compose down

# Remove everything including volumes
docker-compose down -v
```

### Monitoring & Logs

```bash
# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend

# Check service status
docker-compose ps

# Check resource usage
docker stats

# Health check
./scripts/healthcheck.sh
```

### Database Operations

```bash
# Access PostgreSQL
docker-compose exec postgres psql -U chatbot -d chatbot

# Access Redis CLI
docker-compose exec redis redis-cli

# Backup databases
docker-compose exec backend /app/scripts/backup.sh

# Restore databases
docker-compose exec backend /app/scripts/restore.sh postgres /backup/postgres/dump_20240101_120000.sql.gz
```

### Debugging

```bash
# Access backend shell
docker-compose exec backend bash

# Access frontend shell
docker-compose exec frontend sh

# Run tests in container
docker-compose exec backend pytest

# Check environment variables
docker-compose exec backend env

# Debug with additional tools
docker-compose --profile debug up -d
```

## Production Deployment

### SSL/TLS Setup

1. **Using Let's Encrypt:**
```bash
# Install certbot
docker run -it --rm \
  -v /etc/letsencrypt:/etc/letsencrypt \
  -v /var/lib/letsencrypt:/var/lib/letsencrypt \
  certbot/certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email your@email.com \
  --agree-tos \
  --no-eff-email \
  -d yourdomain.com
```

2. **Copy certificates:**
```bash
mkdir -p nginx/ssl
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/
cp /etc/letsencrypt/live/yourdomain.com/chain.pem nginx/ssl/
```

### Environment Variables

Create `.env` file for production:
```env
# API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Database
DB_USER=chatbot
DB_PASSWORD=strong-password-here
DB_NAME=chatbot

# Application
VERSION=1.0.0
API_URL=https://api.yourdomain.com
WS_URL=wss://api.yourdomain.com/ws
CORS_ORIGINS=["https://yourdomain.com"]

# Security
SECRET_KEY=generate-random-secret-key
```

### Zero-Downtime Deployment

```bash
# Build new images
docker-compose -f docker-compose.prod.yml build

# Rolling update for backend
docker-compose -f docker-compose.prod.yml up -d --no-deps --scale backend=6 backend
sleep 30
docker-compose -f docker-compose.prod.yml up -d --no-deps --scale backend=3 backend

# Rolling update for frontend
docker-compose -f docker-compose.prod.yml up -d --no-deps --scale frontend=4 frontend
sleep 30
docker-compose -f docker-compose.prod.yml up -d --no-deps --scale frontend=2 frontend
```

## Monitoring

### Access Monitoring Tools

- **Prometheus:** http://localhost:9090 (production only)
- **Grafana:** http://localhost:3001 (production only)
- **Adminer:** http://localhost:8080 (development with `--profile debug`)
- **Redis Commander:** http://localhost:8081 (development with `--profile debug`)

### Health Checks

```bash
# Run comprehensive health check
./scripts/healthcheck.sh

# Check specific service
curl http://localhost:8000/health
curl http://localhost:3000/api/health

# Check metrics
curl http://localhost:8000/metrics
```

## Troubleshooting

### Common Issues

1. **Port already in use:**
```bash
# Find process using port
lsof -i :8000
# Kill process
kill -9 <PID>
```

2. **Container won't start:**
```bash
# Check logs
docker-compose logs backend
# Check container status
docker ps -a
# Inspect container
docker inspect chatbot-backend
```

3. **Database connection issues:**
```bash
# Test connection
docker-compose exec backend python -c "
from chatbot_ai_system.database import test_connection
test_connection()
"
```

4. **Redis connection issues:**
```bash
# Test Redis connection
docker-compose exec redis redis-cli ping
```

5. **Out of disk space:**
```bash
# Clean up unused images
docker system prune -a
# Clean up volumes
docker volume prune
```

### Performance Tuning

1. **Increase container resources:**
```yaml
# In docker-compose.prod.yml
deploy:
  resources:
    limits:
      cpus: '4'
      memory: 2G
```

2. **Optimize PostgreSQL:**
```bash
# Edit postgresql.conf
docker-compose exec postgres vi /var/lib/postgresql/data/postgresql.conf
```

3. **Optimize Redis:**
```bash
# Edit redis.conf
vi redis/redis.conf
# Restart Redis
docker-compose restart redis
```

## Security Best Practices

1. **Use secrets management:**
   - Never commit secrets to git
   - Use Docker secrets in production
   - Rotate keys regularly

2. **Network isolation:**
   - Use custom networks
   - Limit exposed ports
   - Use firewall rules

3. **Image security:**
   - Scan images for vulnerabilities
   - Use minimal base images
   - Keep images updated

4. **Access control:**
   - Use strong passwords
   - Limit database access
   - Enable Redis AUTH

## Backup & Recovery

### Automated Backups

```bash
# Schedule backups with cron
0 2 * * * docker-compose exec backend /app/scripts/backup.sh
```

### Manual Backup

```bash
# Backup all data
docker-compose exec backend /app/scripts/backup.sh

# Copy backups to host
docker cp chatbot-backend:/backup ./backups
```

### Restore from Backup

```bash
# List available backups
docker-compose exec backend /app/scripts/restore.sh list

# Restore specific backup
docker-compose exec backend /app/scripts/restore.sh postgres /backup/postgres/dump_20240101_120000.sql.gz
```

## Scaling Guidelines

### Horizontal Scaling

```bash
# Scale backend
docker-compose -f docker-compose.prod.yml up -d --scale backend=5

# Scale frontend
docker-compose -f docker-compose.prod.yml up -d --scale frontend=3
```

### Load Testing

```bash
# Install k6
brew install k6

# Run load test
k6 run tests/load-test.js
```

## Maintenance

### Update Dependencies

```bash
# Update base images
docker-compose pull

# Rebuild with new dependencies
docker-compose build --no-cache
```

### Database Migrations

```bash
# Run migrations
docker-compose exec backend python -m chatbot_ai_system.database.migrations
```

### Clear Caches

```bash
# Clear Redis cache
docker-compose exec redis redis-cli FLUSHALL

# Clear nginx cache
docker-compose exec nginx rm -rf /var/cache/nginx/*
```

## Support

For issues and questions:
- Check logs: `docker-compose logs`
- Run health check: `./scripts/healthcheck.sh`
- Review documentation: [Main README](README.md)
- Open an issue: [GitHub Issues](https://github.com/yourusername/chatbot-ai-system/issues)
