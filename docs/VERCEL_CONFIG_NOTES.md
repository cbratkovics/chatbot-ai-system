# Vercel Configuration Architecture Notes

> **Superseded (2026-09-08).** This document predates the demo's current design and describes a
> WebSocket-based frontend and manual deployment steps that no longer exist. The demo streams over
> Server-Sent Events (ADR 0005) and the frontend ships no WebSocket client. Current instructions:
> [`frontend/DEPLOYMENT.md`](../frontend/DEPLOYMENT.md), [`render.yaml`](../render.yaml) and the
> README's Quick start. Kept for the full-deployment history only.

## Purpose

This document explains the Vercel configuration architecture for the AI Chatbot System, including why certain design decisions were made and how the configuration files interact with the deployment process.

## Active Configuration File

**Location**: `frontend/vercel.json`

This is the **only active** Vercel configuration file for the project. It is used when deploying the frontend to Vercel with the Root Directory set to `frontend`.

### Why frontend/vercel.json?

1. **Path Resolution**: By using `frontend` as the Vercel Root Directory, all paths in `vercel.json` are relative to the `frontend/` directory, eliminating path resolution conflicts.

2. **Build Context**: The build process runs entirely within the `frontend/` directory, ensuring that:
   - `npm ci` finds the correct `package.json`
   - `@tailwindcss/postcss` is resolved from `node_modules`
   - TypeScript paths (`@/components/*`) resolve correctly
   - Next.js configuration is properly loaded

3. **Deployment Isolation**: Frontend deployment is completely independent of the backend codebase, allowing for:
   - Separate CI/CD pipelines
   - Independent version control
   - Isolated dependency management

## Root vercel.json (Deprecated)

**Location**: `vercel.json` (repository root)

If a `vercel.json` exists at the repository root, it should be **removed** or **ignored** to prevent conflicts.

### Why Remove Root vercel.json?

Root-level `vercel.json` files cause path resolution issues when the Vercel Root Directory is set to a subdirectory:

1. **Conflicting Commands**: If root `vercel.json` contains `"buildCommand": "cd frontend && npm run build"`, it conflicts with the clean build command in `frontend/vercel.json`.

2. **Module Resolution Failures**: Build commands with `cd` cause module resolution to fail:
   ```
   Error: Cannot find module '@tailwindcss/postcss'
   Error: Cannot resolve '@/components/ChatInterface'
   ```

3. **Multiple Configuration Sources**: Having two `vercel.json` files creates ambiguity about which configuration is active.

### Correct Approach

✅ **Do This**:
- Set Vercel Root Directory to `frontend`
- Use `frontend/vercel.json` as the only configuration
- Keep all build commands simple (no `cd` or path changes)

❌ **Don't Do This**:
- Use root `vercel.json` with directory changes
- Use `cd` commands in build/install commands
- Split configuration across multiple files

## Production Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT BROWSER                          │
│                     (HTTPS/WSS Connections)                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ├─────────────┐
                                │             │
                                ▼             ▼
                    ┌────────────────┐   ┌──────────────────┐
                    │ VERCEL FRONTEND│   │  VERCEL EDGE     │
                    │   Next.js 15   │   │   (API Rewrites) │
                    │  TypeScript    │   │                  │
                    │  Tailwind v4   │   │  /api/health →   │
                    └────────────────┘   └──────────────────┘
                            │                     │
                            │                     │
                            ▼                     ▼
                    ┌─────────────────────────────────────┐
                    │      RENDER BACKEND API             │
                    │  FastAPI (Python)                   │
                    │  https://chatbot-ai-system.         │
                    │         onrender.com                │
                    └─────────────────────────────────────┘
                            │              │
                ┌───────────┴───────┐      │
                │                   │      │
                ▼                   ▼      ▼
        ┌───────────────┐   ┌────────────────────┐
        │ RENDER REDIS  │   │ PINECONE VECTOR DB │
        │  Cache Layer  │   │                    │
        │               │   │ Index: chatbot-    │
        │ chatbot-redis │   │   ai-system        │
        │  instance     │   │ Dims: 1024         │
        │               │   │ Metric: cosine     │
        └───────────────┘   └────────────────────┘
```

## Component Descriptions

### 1. Vercel Frontend (Next.js)

**Responsibilities**:
- Serve the React-based chat interface
- Handle client-side routing
- Manage WebSocket connections
- Display streaming responses
- Show cache hit/miss indicators
- Render Pinecone similarity scores

**Configuration**:
- Framework: Next.js 15.4.5
- React: 19.1.0
- Styling: Tailwind CSS v4
- Path Aliases: `@/` → `./` (tsconfig.json)

**Environment Variables**:
- `NEXT_PUBLIC_API_URL`: Backend API base URL
- `NEXT_PUBLIC_WS_URL`: WebSocket endpoint URL
- Feature flags for cache, streaming, etc.

### 2. Vercel Edge (API Rewrites)

**Purpose**:
Proxy specific API routes to the backend to simplify CORS and provide a unified domain for API calls.

**Configuration** (in `frontend/vercel.json`):
```json
"rewrites": [
  {
    "source": "/api/health",
    "destination": "https://chatbot-ai-system.onrender.com/health"
  }
]
```

**Benefits**:
- Avoids CORS preflight for health checks
- Provides failover capability
- Simplifies frontend configuration

### 3. Render Backend API (FastAPI)

**Responsibilities**:
- Process chat requests via REST API
- Stream responses via WebSocket (`/ws/chat`)
- Query Pinecone for semantic search
- Cache responses in Redis
- Return cache hit/miss metadata

**Endpoints**:
- `GET /health`: Health check with service status
- `POST /api/v1/chat`: Standard chat completion
- `WS /ws/chat`: Streaming chat via WebSocket
- `POST /api/v1/search`: Vector similarity search

**CORS Configuration**:
Must allow origins:
- `https://*.vercel.app`
- `https://your-domain.vercel.app`
- `http://localhost:3000` (development)

### 4. Render Redis (Cache Layer)

**Instance**: `chatbot-redis`

**Responsibilities**:
- Cache API responses to reduce latency
- Store session data
- Track conversation history
- Implement rate limiting

**Configuration**:
- Connection: Internal Render URL
- TTL: Configurable per response type
- Eviction: LRU (Least Recently Used)

**Cache Key Format**:
```
cache:chat:{model}:{hash(prompt)}
cache:search:{hash(query)}
```

### 5. Pinecone Vector Database

**Index**: `chatbot-ai-system`

**Configuration**:
- **Dimensions**: 1024 (embedding vector size)
- **Metric**: Cosine similarity
- **Pods**: Based on Pinecone plan

**Responsibilities**:
- Store document embeddings
- Perform semantic similarity search
- Return relevant context for RAG
- Provide similarity scores

**Query Parameters**:
- `top_k`: Number of results (typically 5-10)
- `include_metadata`: Include document metadata
- `namespace`: Optional query namespace

## Integration Flow

### Standard Chat Request

```
1. User types message in Vercel Frontend
   ↓
2. Frontend sends POST to /api/v1/chat
   ↓
3. Request hits Render Backend (FastAPI)
   ↓
4. Backend checks Redis cache
   │
   ├─ CACHE HIT → Return cached response
   │              (X-Cache-Status: HIT)
   │
   └─ CACHE MISS → Process request
                    ↓
                   Query Pinecone for context
                    ↓
                   Generate AI response
                    ↓
                   Store in Redis cache
                    ↓
                   Return response
                   (X-Cache-Status: MISS)
```

### WebSocket Streaming Request

```
1. User types message in Vercel Frontend
   ↓
2. Frontend opens WebSocket: wss://chatbot-ai-system.onrender.com/ws/chat
   ↓
3. WebSocket established with Render Backend
   ↓
4. Backend sends connection confirmation
   ↓
5. Frontend sends message via WebSocket
   ↓
6. Backend queries Pinecone for context
   ↓
7. Backend streams tokens as they're generated
   │
   ├─ Frontend receives tokens in real-time
   │  └─ Updates UI incrementally
   │
   └─ Backend sends final metadata
      (includes similarity scores, cache status)
```

## Security Configuration

### Content Security Policy

Defined in `frontend/vercel.json`:

```
default-src 'self';
script-src 'self' 'unsafe-eval' 'unsafe-inline';
style-src 'self' 'unsafe-inline';
connect-src 'self'
  https://chatbot-ai-system.onrender.com
  wss://chatbot-ai-system.onrender.com
  https://*.pinecone.io;
font-src 'self' data:;
img-src 'self' data: https:;
frame-ancestors 'none';
```

**Why These Rules?**

- `script-src 'unsafe-eval'`: Required for Next.js development and React DevTools
- `style-src 'unsafe-inline'`: Required for Tailwind CSS and CSS-in-JS
- `connect-src` includes:
  - Render backend (REST API)
  - Render backend WebSocket
  - Pinecone API (for client-side queries, if needed)
- `frame-ancestors 'none'`: Prevent clickjacking

### Additional Security Headers

All defined in `frontend/vercel.json`:

- **X-Frame-Options**: `DENY` (prevent embedding)
- **X-Content-Type-Options**: `nosniff` (prevent MIME sniffing)
- **X-XSS-Protection**: `1; mode=block` (legacy XSS protection)
- **Referrer-Policy**: `origin-when-cross-origin` (controlled referrer)
- **Permissions-Policy**: Disable camera, microphone, geolocation

## Environment-Specific Configuration

### Development (Local)

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

**Characteristics**:
- Backend runs locally
- Redis may be local or remote
- Hot reload enabled
- Debug logging active

### Preview (Vercel)

```bash
NEXT_PUBLIC_API_URL=https://chatbot-ai-system.onrender.com
NEXT_PUBLIC_WS_URL=wss://chatbot-ai-system.onrender.com
```

**Characteristics**:
- Deployed on branch push/PR
- Uses production backend
- Isolated preview URLs
- Full feature parity with production

### Production (Vercel)

```bash
NEXT_PUBLIC_API_URL=https://chatbot-ai-system.onrender.com
NEXT_PUBLIC_WS_URL=wss://chatbot-ai-system.onrender.com
NODE_ENV=production
```

**Characteristics**:
- Optimized build
- Minified assets
- CDN caching
- Analytics enabled

## Build Process

### Vercel Build Steps

When deploying to Vercel with Root Directory = `frontend`:

1. **Install Dependencies**
   ```bash
   npm ci
   ```
   - Installs from `frontend/package.json`
   - Uses `package-lock.json` for reproducibility
   - Includes `@tailwindcss/postcss` from devDependencies

2. **Build Application**
   ```bash
   npm run build
   ```
   - Runs Next.js build process
   - Compiles TypeScript
   - Processes Tailwind CSS with PostCSS
   - Optimizes images and assets
   - Generates static pages

3. **Output**
   - Directory: `frontend/.next`
   - Contains:
     - Server-side routes
     - Static pages
     - Client bundles
     - Image optimization manifest

### Why This Works

✅ **Correct Module Resolution**:
- All `npm` commands run in `frontend/` directory
- `node_modules` is in the same directory
- No path traversal needed

✅ **TypeScript Path Aliases**:
- `@/components` resolves to `frontend/components`
- All imports work correctly

✅ **Tailwind CSS**:
- PostCSS finds `postcss.config.mjs`
- Tailwind plugin loads from `node_modules`
- CSS compiles without errors

## Troubleshooting Path Issues

### Problem: Module Not Found

```
Error: Cannot find module '@tailwindcss/postcss'
```

**Cause**: Build command running in wrong directory or incorrect Root Directory setting.

**Solution**:
1. Set Vercel Root Directory to `frontend`
2. Remove any `cd` commands from `vercel.json`
3. Ensure `frontend/package.json` includes the module in devDependencies

### Problem: Cannot Resolve Import

```
Error: Cannot resolve '@/components/ChatInterface'
```

**Cause**: TypeScript path alias configuration not found or incorrect.

**Solution**:
1. Verify `frontend/tsconfig.json` has correct `paths` configuration
2. Ensure Root Directory is `frontend`
3. Check that component file exists at correct path

### Problem: Conflicting Configuration

```
Warning: Multiple vercel.json files detected
```

**Cause**: Both root and frontend `vercel.json` exist.

**Solution**:
1. Remove or rename root `vercel.json`
2. Keep only `frontend/vercel.json`
3. Clear Vercel cache and redeploy

## Best Practices

### DO

✅ Use `frontend/` as Vercel Root Directory
✅ Keep `vercel.json` in the `frontend/` directory
✅ Use simple build commands without path changes
✅ Set all environment variables in Vercel Dashboard
✅ Include comprehensive security headers
✅ Configure CSP to allow all required origins
✅ Use HTTPS/WSS for all production connections

### DON'T

❌ Use root `vercel.json` with subdirectory builds
❌ Use `cd` commands in build configuration
❌ Hardcode API URLs in source code
❌ Expose secrets in client-side code
❌ Disable security headers for convenience
❌ Mix HTTP and HTTPS connections
❌ Skip CORS configuration on backend

## Version History

- **v1.1.0** (Current):
  - Production-ready Vercel configuration
  - Full integration with Render, Redis, and Pinecone
  - Comprehensive security headers
  - WebSocket streaming support
  - Cache integration

- **v1.0.0**:
  - Initial deployment setup
  - Basic Next.js frontend
  - REST API integration

## References

- [Vercel Configuration Documentation](https://vercel.com/docs/project-configuration)
- [Next.js Deployment Documentation](https://nextjs.org/docs/deployment)
- [Render Documentation](https://render.com/docs)
- [Pinecone Documentation](https://docs.pinecone.io/)

---

**Last Updated**: 2025-10-10
**Maintained By**: Development Team
**Related Files**:
- `frontend/vercel.json`
- `frontend/DEPLOYMENT.md`
- `frontend/package.json`
- `frontend/tsconfig.json`
