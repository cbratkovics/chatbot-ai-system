# Production Deployment Guide

## Overview

This guide covers deploying chatbot-ai-system to production using:
- **Vercel** for Next.js frontend hosting
- **Render** for FastAPI backend hosting
- **Render Redis** for caching layer

**Estimated deployment time**: 30-45 minutes
**Monthly cost**: $14 + AI API usage

## Prerequisites

Before you begin, ensure you have:

- [ ] GitHub account with your repository
- [ ] Vercel account (free tier works) - https://vercel.com
- [ ] Render account (requires payment for Redis) - https://render.com
- [ ] OpenAI API key (required) - https://platform.openai.com/api-keys
- [ ] Anthropic API key (optional) - https://console.anthropic.com/
- [ ] Basic understanding of environment variables
- [ ] Git repository pushed to GitHub

## Architecture Overview

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────┐
│                 │         │                  │         │             │
│  Vercel         │ HTTPS   │  Render          │  Redis  │  Render     │
│  Next.js        ├────────►│  FastAPI         ├────────►│  Redis      │
│  Frontend       │ WSS     │  Backend         │         │  Cache      │
│                 │         │                  │         │             │
└─────────────────┘         └──────────────────┘         └─────────────┘
       │                             │
       │                             │
       └─────────────┬───────────────┘
                     ▼
              User's Browser
```

## Part 1: Backend Deployment (Render)

### Step 1: Create Render Account

1. Visit https://render.com
2. Click "Get Started" or "Sign Up"
3. Sign up with GitHub (recommended for easier integration)
4. Verify your email address
5. Complete account setup

### Step 2: Deploy Redis Cache

Redis provides caching for chat responses and semantic search.

1. From Render dashboard, click **"New +"** button
2. Select **"Redis"**
3. Configure Redis:
   - **Name**: `chatbot-redis`
   - **Plan**: Starter ($7/month)
   - **Region**: Oregon (or closest to your users)
   - **Maxmemory Policy**: `allkeys-lru` (already set in render.yaml)
4. Click **"Create Redis"**
5. Wait for deployment (1-2 minutes)
6. Note the Redis URL (will be auto-connected via render.yaml)

**Important**: Redis instance must be created before deploying the backend service.

### Step 3: Deploy Backend Service

1. From Render dashboard, click **"New +"** button
2. Select **"Web Service"**
3. Choose **"Build and deploy from a Git repository"**
4. Click **"Next"**
5. Connect your GitHub repository:
   - Click **"Connect account"** if not already connected
   - Select your chatbot-ai-system repository
   - Click **"Connect"**

6. Render will auto-detect `render.yaml` configuration
   - If asked, confirm you want to use the render.yaml file
   - The configuration includes all necessary settings

7. Review the auto-detected settings:
   - **Name**: chatbot-ai-backend
   - **Environment**: Python
   - **Build Command**: `pip install poetry && poetry install --only main`
   - **Start Command**: `poetry run uvicorn chatbot_ai_system.server.main:app --host 0.0.0.0 --port $PORT --workers 2`

8. Click **"Create Web Service"**

### Step 4: Configure Environment Variables

After the service is created, add your API keys:

1. In your service dashboard, click **"Environment"** tab
2. Add the following secret environment variables:

   | Key | Value | Notes |
   |-----|-------|-------|
   | `OPENAI_API_KEY` | Your OpenAI API key | Required |
   | `ANTHROPIC_API_KEY` | Your Anthropic API key | Optional |

3. All other environment variables are pre-configured in render.yaml

**Important**: Never commit API keys to your repository.

### Step 5: Monitor Backend Deployment

1. Click **"Logs"** tab to watch deployment progress
2. Deployment takes 5-10 minutes for first build
3. Look for success message: `Application startup complete`
4. Service status should show **"Live"** with a green dot

### Step 6: Verify Backend Deployment

Test your backend endpoints:

1. **Health Check**:
   ```bash
   curl https://your-app-name.onrender.com/health
   ```
   Expected response:
   ```json
   {
     "status": "healthy",
     "version": "1.0.0",
     "service": "chatbot-ai-system",
     "timestamp": "2024-01-01T00:00:00.000000",
     "environment": "production",
     "checks": {
       "redis": "healthy",
       "ai_providers": "configured: openai"
     }
   }
   ```

2. **API Documentation**:
   Visit: `https://your-app-name.onrender.com/docs`
   Should display interactive API documentation

3. **Check Logs**:
   - No error messages in logs
   - Redis connection successful
   - AI providers configured

**Important**: Note your backend URL for frontend configuration.

## Part 2: Frontend Deployment (Vercel)

### Step 1: Update Frontend Configuration

1. Update `frontend/.env.production` with your actual backend URL:
   ```bash
   NEXT_PUBLIC_API_URL=https://your-backend-name.onrender.com
   NEXT_PUBLIC_WS_URL=wss://your-backend-name.onrender.com
   NODE_ENV=production
   ```

2. Replace `your-backend-name` with your actual Render service name

### Step 2: Test Build Locally (Optional but Recommended)

```bash
cd frontend
npm ci
npm run build
npm start
```

Visit http://localhost:3000 and verify the application works.

### Step 3: Deploy to Vercel

**Option A: Vercel CLI (Recommended)**

1. Install Vercel CLI:
   ```bash
   npm install -g vercel
   ```

2. Login to Vercel:
   ```bash
   vercel login
   ```

3. Deploy:
   ```bash
   cd frontend
   vercel --prod
   ```

4. Follow prompts:
   - Link to existing project or create new
   - Confirm project settings
   - Wait for deployment

**Option B: Vercel Dashboard**

1. Visit https://vercel.com/dashboard
2. Click **"New Project"**
3. Import your repository:
   - Select your GitHub repository
   - Click **"Import"**
4. Configure project:
   - **Framework Preset**: Next.js (auto-detected)
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build` (auto-detected)
   - **Output Directory**: `.next` (auto-detected)
5. Add environment variables:
   - Click **"Environment Variables"**
   - Add `NEXT_PUBLIC_API_URL` = Your Render backend URL
   - Add `NEXT_PUBLIC_WS_URL` = Your Render WebSocket URL (wss://)
6. Click **"Deploy"**

### Step 4: Configure Environment Variables in Vercel

If you used the dashboard method without setting env vars:

1. Go to your project settings
2. Click **"Environment Variables"**
3. Add:
   - `NEXT_PUBLIC_API_URL` = `https://your-backend.onrender.com`
   - `NEXT_PUBLIC_WS_URL` = `wss://your-backend.onrender.com`
4. Redeploy from **"Deployments"** tab

### Step 5: Verify Frontend Deployment

1. Visit your Vercel URL (e.g., `https://your-project.vercel.app`)
2. Check that the application loads
3. Open browser DevTools (F12) → Console tab
4. Verify no errors
5. Test sending a chat message
6. Verify WebSocket connection (Network tab → WS)

## Part 3: Update Backend CORS Configuration

Now that frontend is deployed, update backend to allow requests from Vercel:

### Step 1: Update CORS in Render

1. Go to Render dashboard
2. Select your backend service
3. Click **"Environment"** tab
4. Find `CORS_ORIGINS` variable
5. Update value to:
   ```json
   ["https://your-actual-domain.vercel.app","http://localhost:3000"]
   ```
6. Replace `your-actual-domain` with your real Vercel domain

### Step 2: Redeploy Backend

1. Click **"Manual Deploy"** → **"Deploy latest commit"**
2. Wait for deployment to complete
3. Verify in logs that CORS is updated

### Step 3: Test CORS

1. Visit your Vercel app
2. Send a chat message
3. Check Network tab in DevTools
4. Verify no CORS errors

## Part 4: Production Verification

### Backend Tests

Run these tests to verify backend is working:

1. **Health Check**:
   ```bash
   curl https://your-backend.onrender.com/health | jq
   ```

2. **Chat Endpoint** (requires valid API key):
   ```bash
   curl -X POST https://your-backend.onrender.com/api/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{
       "messages": [{"role": "user", "content": "Hello"}],
       "model": "gpt-3.5-turbo"
     }' | jq
   ```

3. **Models Endpoint**:
   ```bash
   curl https://your-backend.onrender.com/api/v1/chat/models | jq
   ```

### Frontend Tests

1. Load application in browser
2. Open DevTools → Console
3. Verify no errors
4. Test features:
   - [ ] Send chat message
   - [ ] Receive response
   - [ ] Streaming works
   - [ ] WebSocket connection stable
   - [ ] Error handling works
   - [ ] Reconnection after disconnect

### Integration Tests

1. **End-to-End Chat**:
   - Send message
   - Verify streaming response
   - Check response appears in UI
   - Verify conversation history works

2. **WebSocket Reconnection**:
   - Open DevTools → Network → WS
   - Close backend (Manual Deploy → Stop)
   - Verify frontend shows disconnected
   - Restart backend
   - Verify frontend reconnects automatically

3. **Error Handling**:
   - Send invalid request
   - Verify error message displays
   - Verify app doesn't crash

## Part 5: Monitoring and Maintenance

### Set Up Monitoring

1. **Render Monitoring**:
   - Enable email alerts for service failures
   - Monitor CPU and memory usage in dashboard
   - Set up log retention

2. **Vercel Monitoring**:
   - Check function execution times
   - Monitor bandwidth usage
   - Review error logs

3. **External Monitoring** (Optional):
   - Set up UptimeRobot: https://uptimerobot.com
   - Monitor backend health endpoint
   - Get alerts when service is down

### Monitor Costs

1. **Render**:
   - Web Service: $7/month (Starter)
   - Redis: $7/month (Starter)
   - Total: $14/month

2. **Vercel**:
   - Free tier is sufficient for most use cases
   - Upgrade to Pro ($20/month) if you need:
     - More bandwidth
     - More function executions
     - Team features

3. **AI API Usage**:
   - OpenAI: https://platform.openai.com/usage
   - Anthropic: https://console.anthropic.com/
   - Set up billing alerts
   - Monitor token usage

### Maintenance Tasks

**Weekly**:
- [ ] Check error logs in Render and Vercel
- [ ] Monitor API usage and costs
- [ ] Review performance metrics

**Monthly**:
- [ ] Review and optimize API usage
- [ ] Update dependencies if needed
- [ ] Review security advisories
- [ ] Backup any data

**As Needed**:
- [ ] Scale Render service if traffic increases
- [ ] Optimize Redis memory usage
- [ ] Update environment variables
- [ ] Deploy new features

## Troubleshooting

### Backend Issues

**Problem**: Health check returns 503
- Check Redis connection in health response
- Verify Redis instance is running
- Check REDIS_URL is correctly set

**Problem**: API keys not working
- Verify keys are set in Render environment variables
- Check keys are valid in provider dashboards
- Look for authentication errors in logs

**Problem**: Build fails
- Check logs for specific error
- Verify pyproject.toml dependencies are correct
- Ensure Python version matches (3.11+)

### Frontend Issues

**Problem**: Application doesn't load
- Check Vercel build logs
- Verify Next.js build succeeded
- Check for JavaScript errors in console

**Problem**: Can't connect to backend
- Verify NEXT_PUBLIC_API_URL is correct
- Check CORS configuration in backend
- Look for network errors in DevTools

**Problem**: WebSocket connection fails
- Verify NEXT_PUBLIC_WS_URL uses `wss://` protocol
- Check WebSocket endpoint is accessible
- Review backend WebSocket logs

### CORS Errors

**Problem**: CORS policy error in browser

**Solution**:
1. Verify Vercel domain is in CORS_ORIGINS
2. Format must be JSON array: `["https://domain.vercel.app"]`
3. No trailing slashes
4. Redeploy backend after changes

### Rate Limiting

**Problem**: 429 Too Many Requests

**Solution**:
1. Rate limit is 100 requests/minute by default
2. Adjust in Render environment: `RATE_LIMIT_REQUESTS=200`
3. Or increase period: `RATE_LIMIT_PERIOD=120`

## Scaling Guide

### When to Scale

Scale your deployment when you experience:
- High latency (>3s response times)
- Frequent timeouts
- Redis memory warnings
- CPU/memory at >80% consistently

### Scaling Options

**Backend (Render)**:
1. Upgrade to Standard plan ($25/month)
   - More CPU and memory
   - Better performance
2. Increase workers in start command:
   ```
   --workers 4
   ```

**Redis (Render)**:
1. Upgrade to Standard plan ($25/month)
   - More memory
   - Better performance

**Frontend (Vercel)**:
1. Pro plan ($20/month) if hitting limits
2. Edge functions for better global performance

## Security Best Practices

### API Keys

- Never commit API keys to repository
- Use environment variables for all secrets
- Rotate keys periodically
- Monitor for unauthorized usage

### CORS

- Only allow specific domains
- Never use wildcard (*) in production
- Keep localhost only for development

### Rate Limiting

- Keep rate limits enabled
- Adjust based on legitimate traffic
- Monitor for abuse patterns

### HTTPS

- Always use HTTPS (enforced by Render/Vercel)
- Verify SSL certificates are valid
- Use wss:// for WebSocket connections

## Rollback Procedures

### Backend Rollback

If new backend deployment causes issues:

1. Go to Render dashboard
2. Select your service
3. Click **"Manual Deploy"**
4. Select **"Deploy previous commit"**
5. Choose last known good commit
6. Click **"Deploy"**

### Frontend Rollback

If new frontend deployment causes issues:

1. Go to Vercel dashboard
2. Select your project
3. Click **"Deployments"**
4. Find last successful deployment
5. Click **"..."** menu → **"Promote to Production"**

## Additional Resources

### Documentation

- Render Docs: https://render.com/docs
- Vercel Docs: https://vercel.com/docs
- FastAPI Docs: https://fastapi.tiangolo.com
- Next.js Docs: https://nextjs.org/docs

### Support

- Render Support: support@render.com
- Vercel Support: https://vercel.com/support
- OpenAI Support: https://help.openai.com
- Anthropic Support: support@anthropic.com

### Community

- GitHub Issues: Create issues for bugs
- Discussions: Ask questions in repository discussions

## Conclusion

You should now have a fully deployed, production-ready chatbot system running on Vercel and Render. The system includes:

- Frontend hosted on Vercel with global CDN
- Backend API on Render with autoscaling
- Redis cache for improved performance
- WebSocket support for real-time streaming
- Comprehensive error handling and monitoring

Total infrastructure cost: $14/month + AI API usage

For questions or issues, refer to the troubleshooting section or create an issue in the repository.
