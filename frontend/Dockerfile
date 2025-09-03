# Multi-stage build for production-ready frontend
# Stage 1: Dependencies
FROM node:18-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./
RUN npm ci --only=production

# Stage 2: Builder
FROM node:18-alpine AS builder
WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build arguments
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WS_URL

# Set build-time env variables
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_WS_URL=${NEXT_PUBLIC_WS_URL}
ENV NEXT_TELEMETRY_DISABLED=1

# Build the application
RUN npm run build

# Stage 3: Production image with Nginx
FROM nginx:alpine-slim

# Install Node.js for Next.js server (standalone mode)
RUN apk add --no-cache nodejs npm tini

# Create non-root user
RUN addgroup -g 1000 -S nextjs && \
    adduser -S nextjs -u 1000 -G nextjs

# Copy Nginx configuration
COPY --chown=nextjs:nextjs nginx/nginx.conf /etc/nginx/nginx.conf
COPY --chown=nextjs:nextjs nginx/default.conf /etc/nginx/conf.d/default.conf

# Create necessary directories
RUN mkdir -p /app /var/cache/nginx /var/log/nginx && \
    chown -R nextjs:nextjs /app /var/cache/nginx /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R nextjs:nextjs /var/run/nginx.pid

# Copy Next.js standalone build
WORKDIR /app
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nextjs /app/public ./public

# Security headers and optimizations
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:3000/api/health || exit 1

# Expose ports
EXPOSE 3000 80

# Use non-root user
USER nextjs

# Start both Nginx and Next.js
CMD ["sh", "-c", "nginx && exec node server.js"]