# Frontend Deployment Guide

## Production Architecture

This Next.js frontend is deployed on **Vercel** and integrates with the following backend services:

- **Backend API**: FastAPI on Render at `https://chatbot-ai-system.onrender.com`
- **Cache Layer**: Redis on Render (chatbot-redis instance)
- **Vector Database**: Pinecone (chatbot-ai-system index, 1024 dimensions, cosine similarity)

## Vercel Configuration

### Project Settings

When deploying to Vercel, use these exact settings:

1. **Root Directory**: `frontend`
2. **Framework Preset**: Next.js (auto-detected)
3. **Build Command**: `npm run build` (default)
4. **Output Directory**: `.next` (default)
5. **Install Command**: `npm ci` (default)
6. **Node Version**: 20.x (recommended)

### Required Environment Variables

Set these environment variables in the Vercel Dashboard (Settings > Environment Variables):

```bash
# Production API Configuration
NEXT_PUBLIC_API_URL=https://chatbot-ai-system.onrender.com
NEXT_PUBLIC_WS_URL=wss://chatbot-ai-system.onrender.com

# Node Environment
NODE_ENV=production

# Feature Flags
NEXT_PUBLIC_ENABLE_CACHE=true
NEXT_PUBLIC_ENABLE_STREAMING=true
NEXT_PUBLIC_ENABLE_DARK_MODE=true

# Default Model Settings
NEXT_PUBLIC_DEFAULT_MODEL=gpt-3.5-turbo
NEXT_PUBLIC_DEFAULT_TEMPERATURE=0.7
NEXT_PUBLIC_MAX_TOKENS=2048

# WebSocket Configuration
NEXT_PUBLIC_WS_RECONNECT_INTERVAL=5000
NEXT_PUBLIC_WS_MAX_RECONNECT_ATTEMPTS=5
NEXT_PUBLIC_WS_HEARTBEAT_INTERVAL=30000

# UI Configuration
NEXT_PUBLIC_APP_NAME=AI Chatbot System
NEXT_PUBLIC_THEME_COLOR=#000000
```

**Important**: All variables must be set for **Production**, **Preview**, and **Development** environments in Vercel.

## Backend CORS Configuration

The FastAPI backend must be configured to allow requests from your Vercel deployment:

### Required CORS Origins

Add these origins to the backend's CORS configuration:

```python
# In backend FastAPI app configuration
CORS_ORIGINS = [
    "https://your-vercel-domain.vercel.app",
    "https://*.vercel.app",  # For preview deployments
    "http://localhost:3000",  # For local development
]
```

### CORS Headers Required

The backend must send these headers:

- `Access-Control-Allow-Origin`
- `Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS`
- `Access-Control-Allow-Headers: Content-Type, Authorization`
- `Access-Control-Allow-Credentials: true`

### WebSocket Configuration

Ensure the backend supports WebSocket connections:

- Path: `/ws/chat`
- Protocol: `wss://` (secure WebSocket)
- Connection timeout: 300 seconds minimum
- Ping/pong heartbeat: Every 30 seconds

## Integration Verification

After deployment, verify each integration point:

### 1. Backend API Health Check

```bash
curl https://chatbot-ai-system.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.1.0",
  "redis": "connected",
  "pinecone": "connected"
}
```

### 2. Redis Cache Verification

Test cache operations through the API:

```bash
curl -X POST https://chatbot-ai-system.onrender.com/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "use_cache": true}'
```

Check response headers for cache indicators:
- `X-Cache-Status: HIT` (cached response)
- `X-Cache-Status: MISS` (new response)

### 3. Pinecone Vector Search

Verify semantic search is working:

```bash
curl -X POST https://chatbot-ai-system.onrender.com/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "top_k": 5}'
```

Expected response should include:
- `similarity_scores`: Array of scores (0-1 range)
- `matches`: Array of matched documents
- `metadata`: Document metadata with timestamps

### 4. WebSocket Connection

Test from browser console on your Vercel deployment:

```javascript
const ws = new WebSocket('wss://chatbot-ai-system.onrender.com/ws/chat');

ws.onopen = () => {
  console.log('WebSocket connected');
  ws.send(JSON.stringify({ message: 'Hello' }));
};

ws.onmessage = (event) => {
  console.log('Received:', JSON.parse(event.data));
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};
```

### 5. Frontend UI Verification

Visit your Vercel deployment and check:

- [ ] Chat interface loads without errors
- [ ] WebSocket status indicator shows "Connected"
- [ ] Messages send and receive properly
- [ ] Streaming responses work (real-time token display)
- [ ] Cache hit/miss indicators appear in message metadata
- [ ] Pinecone similarity scores display for relevant queries
- [ ] Model selector shows available models
- [ ] Settings panel (temperature, max tokens) works
- [ ] Dark mode toggle functions (if enabled)

## Deployment Checklist

Before deploying to production:

### Backend Services
- [ ] Render backend is running and healthy
- [ ] Redis instance is connected and responsive
- [ ] Pinecone index is accessible and populated
- [ ] CORS origins include Vercel domain
- [ ] WebSocket support is enabled
- [ ] API rate limits are configured
- [ ] Monitoring and logging are active

### Frontend Configuration
- [ ] `frontend/vercel.json` is properly configured
- [ ] All environment variables are set in Vercel Dashboard
- [ ] Security headers are configured (CSP, X-Frame-Options, etc.)
- [ ] API rewrites are pointing to correct backend URL
- [ ] Build completes successfully locally (`npm run build`)
- [ ] No TypeScript errors (`npm run lint`)

### Security
- [ ] Content Security Policy includes all required origins
- [ ] WebSocket connections use `wss://` (secure)
- [ ] API keys are not exposed in client-side code
- [ ] HTTPS is enforced for all connections
- [ ] Frame-ancestors is set to 'none'
- [ ] XSS protection headers are enabled

### Performance
- [ ] Images are optimized (Next.js Image component)
- [ ] Code splitting is enabled (automatic with Next.js)
- [ ] API responses are cached appropriately
- [ ] Redis cache is configured with proper TTL
- [ ] Pinecone queries use appropriate top_k values

## Build Fix Applied (2025-01-11)

### Lightning CSS Binary Issue - RESOLVED

**Root Cause:** Root `vercel.json` with `cd frontend` commands conflicted with Vercel Root Directory setting, causing module resolution failures and missing native binaries.

**Changes Made:**
1. **Removed Root Config Conflict**
   - Renamed root `vercel.json` to `vercel.json.DEPRECATED`
   - Reason: When Vercel Root Directory = `frontend`, build context is already inside frontend/
   - Using `cd frontend` in build commands caused path resolution to break

2. **Added .npmrc Configuration**
   - Created `frontend/.npmrc` with `optional=true`
   - Ensures Lightning CSS platform-specific binaries are installed
   - Required for Linux x64 build environment on Vercel

3. **Added Binary Verification**
   - Created `frontend/scripts/verify-lightningcss.js`
   - Postinstall script checks for native binary after npm install
   - Provides troubleshooting guidance if binary missing

4. **Node Version Pinning** (from previous fix)
   - Node 20.x in package.json engines
   - .nvmrc with "20"
   - Prebuild diagnostics script

### Configuration Architecture

**Correct Setup:**
```
Vercel Dashboard Settings:
  Root Directory: "frontend"
  ↓
  Build context is: /vercel/path0/frontend/
  ↓
  npm ci runs in frontend/
  ↓
  Lightning CSS binaries install to frontend/node_modules/lightningcss/node/
```

**Previous Broken Setup:**
```
Root vercel.json: "cd frontend && npm ci"
  ↓
  Changes directory after build context set
  ↓
  Module resolution confused
  ↓
  Binaries installed to wrong path
```

### Verification After Deploy

1. **Check Vercel Build Logs:**
   ```
   Running "vercel build"
   Vercel CLI 48.x
   Running "install" command: `npm ci`
   [should NOT show "cd frontend"]
   ```

2. **Check Postinstall Output:**
   ```
   Lightning CSS binary found: lightningcss.linux-x64-gnu.node
   ```

3. **Check Build Success:**
   ```
   Creating an optimized production build ...
   ✓ Compiled successfully
   ```

### WebSocket Configuration (Previously Validated)
- Backend endpoint: `/ws/chat` (confirmed live)
- Frontend uses NEXT_PUBLIC_WS_URL directly
- Config module at `lib/config.ts:25-36` auto-normalizes paths
- No manual fixes needed for WebSocket connectivity

### Lightning CSS Optional Dependencies Fix (2025-01-11 - FINAL)

**Root Cause:** npm ci was not installing Lightning CSS's platform-specific binaries even though the main package was present.

**Why .npmrc Failed:**
- `optional=true` is NOT a valid npm configuration option
- npm was rejecting the config with warnings
- Optional dependencies install by default, but npm ci is strict with package-lock.json

**Final Solution (Multi-Layered):**

1. **Added lightningcss-cli to devDependencies**
   - Forces installation of ALL platform binaries
   - CLI package has binaries as regular deps, not optional

2. **Updated .npmrc (removed invalid config)**
   - Removed `optional=true` (invalid)
   - Kept performance optimizations (audit=false, fund=false)

3. **Override Vercel Install Command**
   - Updated `frontend/vercel.json` with `installCommand: "npm ci --include=optional --prefer-offline"`
   - Explicitly tells npm ci to include optional dependencies

4. **Enhanced Verification Script**
   - Shows what files exist in lightningcss/node/
   - Better diagnostics for troubleshooting

**Technical Details:**

Lightning CSS package structure:
```
lightningcss@1.30.1 (main package)
├── index.js
├── optionalDependencies:
│   ├── @lightningcss-linux-x64-gnu (platform binary)
│   ├── @lightningcss-darwin-arm64 (platform binary)
│   └── ... (other platforms)
```

Problem: npm ci with strict lock file was skipping optionalDependencies

Solution: lightningcss-cli explicitly requires all binaries, so adding it as a devDependency guarantees they install.

## Troubleshooting

### Build Failures

**Error**: `Cannot find module '../lightningcss.linux-x64-gnu.node'`
- **Root Cause**: Platform-specific Lightning CSS binary missing or wrong Node version
- **Solution**: Ensure Node 20.x is configured in Vercel project settings
- **Verify**: Check `.nvmrc` file exists in frontend directory with `20` as content
- **Action**: Clear Vercel build cache and redeploy

**Error**: `Cannot find module '@tailwindcss/postcss'`
- **Solution**: Ensure `frontend/package.json` includes `"@tailwindcss/postcss": "^4.1.14"` in dependencies
- **Verify**: Run `npm ci` in the frontend directory

**Error**: `Cannot resolve '@/components/ChatInterface'`
- **Solution**: Ensure Vercel Root Directory is set to `frontend`
- **Verify**: Check that `tsconfig.json` has correct path aliases

**Error**: Build succeeds but runtime errors occur
- **Solution**: Check that all environment variables are set in Vercel Dashboard
- **Verify**: Go to Settings > Environment Variables and ensure all `NEXT_PUBLIC_*` variables are present

### Connection Issues

**WebSocket fails to connect**
- Check that backend WebSocket path is `/ws/chat`
- Verify `NEXT_PUBLIC_WS_URL` uses `wss://` protocol
- Check browser console for CORS errors
- Ensure backend allows WebSocket upgrade requests

**API requests return 403 Forbidden**
- Verify CORS origins include your Vercel domain
- Check that backend CORS configuration allows credentials
- Ensure Content-Type header is set correctly

**Cache not working**
- Verify Redis instance is running on Render
- Check that `NEXT_PUBLIC_ENABLE_CACHE=true`
- Look for `X-Cache-Status` header in API responses
- Check backend logs for Redis connection errors

**Pinecone queries fail**
- Verify Pinecone API key is set in backend environment
- Check that index name matches: `chatbot-ai-system`
- Ensure dimensions are correct: 1024
- Verify similarity metric: cosine

### Performance Issues

**Slow initial load**
- Check Render backend cold start (first request after idle)
- Enable Vercel Edge Functions for API routes if needed
- Verify Redis cache is being used for repeat queries

**Streaming responses delayed**
- Check WebSocket connection stability
- Verify backend streaming is enabled
- Look for network throttling in browser DevTools
- Check Render logs for processing delays

## Rollback Procedure

If a deployment causes issues:

### Immediate Rollback (Vercel)
1. Go to Vercel Dashboard > Deployments
2. Find the last working deployment
3. Click "..." menu > "Promote to Production"
4. Verify rollback was successful

### Backend Rollback (Render)
1. Go to Render Dashboard > chatbot-ai-system service
2. Click "Manual Deploy" > Select previous commit
3. Wait for deployment to complete
4. Verify health check passes

### Verify After Rollback
- [ ] Frontend loads correctly
- [ ] Backend API responds
- [ ] WebSocket connections work
- [ ] Redis cache is operational
- [ ] Pinecone queries return results

## Monitoring

### Key Metrics to Monitor

**Frontend (Vercel Analytics)**
- Page load time
- Time to First Byte (TTFB)
- Core Web Vitals (LCP, FID, CLS)
- Error rate

**Backend (Render + Application Logs)**
- API response time
- WebSocket connection count
- Redis cache hit rate
- Pinecone query latency
- Error rate by endpoint

**Infrastructure**
- Render backend uptime
- Redis memory usage
- Pinecone index stats
- Network latency

### Health Check Endpoints

Monitor these endpoints:

```bash
# Backend health
https://chatbot-ai-system.onrender.com/health

# Frontend (via Vercel rewrite)
https://your-domain.vercel.app/api/health
```

## Support and Resources

- **Vercel Documentation**: https://vercel.com/docs
- **Next.js Documentation**: https://nextjs.org/docs
- **Render Documentation**: https://render.com/docs
- **Pinecone Documentation**: https://docs.pinecone.io/

## Version History

- **v1.1.0** (Current): Production-ready deployment with full integration
  - Vercel frontend configuration
  - Render backend integration
  - Redis cache support
  - Pinecone vector search
  - WebSocket streaming
  - Security headers and CORS

---

**Last Updated**: 2025-10-10
**Maintained By**: Development Team
