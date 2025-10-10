# Production Deployment Checklist

## Pre-Deployment

### Backend (Render)
- [ ] Created render.yaml configuration
- [ ] Set OPENAI_API_KEY in Render dashboard
- [ ] Set ANTHROPIC_API_KEY in Render dashboard
- [ ] Created Redis instance on Render
- [ ] Updated CORS_ORIGINS with actual Vercel domain
- [ ] Verified health check endpoint works locally
- [ ] Tested WebSocket connection locally
- [ ] Reviewed security settings (rate limiting, CORS, etc.)
- [ ] Confirmed Python dependencies in pyproject.toml

### Frontend (Vercel)
- [ ] Created .env.production with backend URL
- [ ] Updated vercel.json with production config
- [ ] Tested API client configuration
- [ ] Verified WebSocket reconnection logic
- [ ] Reviewed security headers
- [ ] Tested build locally: `npm run build`
- [ ] Confirmed all environment variables are set

## Deployment Steps

### 1. Deploy Backend to Render

#### Step 1.1: Create Render Account
- [ ] Sign up at https://render.com
- [ ] Connect GitHub account to Render

#### Step 1.2: Create Redis Instance
1. From Render dashboard, click "New +"
2. Select "Redis"
3. Choose "Starter" plan ($7/month)
4. Name it "chatbot-redis"
5. Click "Create Redis"
6. Wait for deployment to complete
- [ ] Redis instance created and running

#### Step 1.3: Deploy Backend Service
1. From Render dashboard, click "New +"
2. Select "Web Service"
3. Connect your repository
4. Render will auto-detect render.yaml
5. Click "Create Web Service"
- [ ] Backend service created

#### Step 1.4: Configure Environment Variables
In Render dashboard, add these secret environment variables:
- [ ] OPENAI_API_KEY: Your OpenAI API key
- [ ] ANTHROPIC_API_KEY: Your Anthropic API key

Note: All other variables are pre-configured in render.yaml

#### Step 1.5: Update CORS Configuration
After deploying frontend (step 2), update in Render dashboard:
- [ ] Update CORS_ORIGINS with actual Vercel domain
- [ ] Format: `["https://your-actual-domain.vercel.app","http://localhost:3000"]`

#### Step 1.6: Verify Backend Deployment
- [ ] Backend is deployed and running
- [ ] Check https://your-app.onrender.com/health
- [ ] Health check returns: `{"status": "healthy", ...}`
- [ ] Redis connection shows as "healthy" in health check
- [ ] API documentation accessible at https://your-app.onrender.com/docs

### 2. Deploy Frontend to Vercel

#### Step 2.1: Update Environment Variables
1. Edit frontend/.env.production
2. Set NEXT_PUBLIC_API_URL to your Render backend URL
3. Set NEXT_PUBLIC_WS_URL to your Render WebSocket URL
- [ ] Environment variables updated with actual URLs
- [ ] Example: NEXT_PUBLIC_API_URL=https://chatbot-ai-backend.onrender.com

#### Step 2.2: Deploy to Vercel
Option A: Vercel CLI
```bash
cd frontend
npm ci
npm run build  # Test build locally
vercel --prod
```

Option B: Vercel Dashboard
1. Visit https://vercel.com
2. Click "New Project"
3. Import your repository
4. Select "frontend" as root directory
5. Deploy
- [ ] Frontend deployed successfully

#### Step 2.3: Configure Vercel Environment Variables
In Vercel dashboard, add these environment variables:
- [ ] NEXT_PUBLIC_API_URL: Your Render backend URL
- [ ] NEXT_PUBLIC_WS_URL: Your Render WebSocket URL (wss://)
- [ ] Redeploy if environment variables were added after initial deployment

#### Step 2.4: Verify Frontend Deployment
- [ ] Visit your Vercel URL
- [ ] Application loads successfully
- [ ] No console errors in browser DevTools

### 3. Update Backend CORS
Now that frontend is deployed:
- [ ] Update CORS_ORIGINS in Render dashboard
- [ ] Include your actual Vercel domain
- [ ] Redeploy backend service

## Post-Deployment Verification

### Backend Health Checks
- [ ] Health endpoint returns 200: https://your-app.onrender.com/health
- [ ] Redis connection works (check health response)
- [ ] API endpoint accessible: https://your-app.onrender.com/docs
- [ ] CORS headers allow Vercel domain
- [ ] Rate limiting works (test with >100 requests/min)

### Frontend Verification
- [ ] Application loads: https://your-app.vercel.app
- [ ] Can connect to backend API
- [ ] WebSocket connection establishes
- [ ] Can send chat messages
- [ ] Receives streaming responses
- [ ] Error handling works correctly

### Integration Tests
- [ ] End-to-end chat flow works
- [ ] Streaming responses display correctly
- [ ] WebSocket reconnects after disconnect
- [ ] API errors display user-friendly messages
- [ ] Rate limiting prevents abuse
- [ ] Cache system works (if enabled)

### Performance Tests
- [ ] Page load time < 3 seconds
- [ ] API response time < 2 seconds
- [ ] WebSocket connection time < 1 second
- [ ] No memory leaks in long sessions

## Monitoring Setup

### Render Monitoring
- [ ] Check Render logs for errors
- [ ] Monitor CPU and memory usage
- [ ] Monitor Redis memory usage
- [ ] Set up log retention policy

### Vercel Monitoring
- [ ] Check Vercel logs for errors
- [ ] Monitor function execution times
- [ ] Monitor bandwidth usage

### External Monitoring (Optional)
- [ ] Set up UptimeRobot or similar
- [ ] Configure health check alerts
- [ ] Set up error tracking (Sentry, etc.)
- [ ] Configure performance monitoring

## Security Verification

### Backend Security
- [ ] API keys are set as environment variables (not in code)
- [ ] CORS is properly configured
- [ ] Rate limiting is active
- [ ] HTTPS is enforced
- [ ] Health endpoint doesn't expose sensitive data

### Frontend Security
- [ ] Security headers are set (X-Frame-Options, CSP, etc.)
- [ ] No API keys in frontend code
- [ ] HTTPS is enforced
- [ ] No sensitive data in client-side storage

## Cost Monitoring

### Monthly Infrastructure Costs
- [ ] Render Web Service (Starter): $7/month
- [ ] Render Redis (Starter): $7/month
- [ ] Vercel (Free tier): $0/month
- [ ] Total Infrastructure: $14/month

### Variable Costs
- [ ] OpenAI API usage: Monitor at https://platform.openai.com/usage
- [ ] Anthropic API usage: Monitor at https://console.anthropic.com/
- [ ] Set up billing alerts for AI API usage

## Rollback Plan

### If Deployment Fails

#### Backend Rollback
1. In Render dashboard, go to your service
2. Click "Manual Deploy"
3. Select previous successful deployment
4. Wait for rollback to complete
- [ ] Know how to rollback backend

#### Frontend Rollback
1. In Vercel dashboard, go to your project
2. Click "Deployments"
3. Find previous successful deployment
4. Click "..." menu and select "Promote to Production"
- [ ] Know how to rollback frontend

#### Debugging Steps
1. Check Render logs for backend errors
2. Check Vercel logs for frontend errors
3. Verify environment variables are correct
4. Test endpoints individually
5. Check CORS configuration
- [ ] Understand debugging process

## Documentation

### Post-Deployment Documentation
- [ ] Document actual production URLs
- [ ] Update README with production links
- [ ] Document any configuration changes
- [ ] Update API documentation if changed
- [ ] Document monitoring procedures

### Team Communication
- [ ] Notify team of successful deployment
- [ ] Share production URLs
- [ ] Share monitoring dashboard access
- [ ] Document any known issues
- [ ] Schedule post-deployment review

## Next Steps

### After Successful Deployment
- [ ] Monitor logs for first 24 hours
- [ ] Review performance metrics
- [ ] Test with real users
- [ ] Gather feedback
- [ ] Document lessons learned

### Future Improvements
- [ ] Consider upgrading to paid Vercel plan for advanced features
- [ ] Implement database for conversation history
- [ ] Add authentication/authorization
- [ ] Implement analytics tracking
- [ ] Add more comprehensive error tracking
- [ ] Consider CDN for static assets
- [ ] Implement CI/CD pipeline

## Production URLs

### Backend
- API: https://chatbot-ai-backend.onrender.com
- Health: https://chatbot-ai-backend.onrender.com/health
- Docs: https://chatbot-ai-backend.onrender.com/docs
- WebSocket: wss://chatbot-ai-backend.onrender.com/ws/chat

### Frontend
- Application: https://your-app.vercel.app
- Update after deployment

### Monitoring
- Render Dashboard: https://dashboard.render.com
- Vercel Dashboard: https://vercel.com/dashboard
- OpenAI Usage: https://platform.openai.com/usage
- Anthropic Console: https://console.anthropic.com/

## Support

### Getting Help
- Render Support: https://render.com/docs
- Vercel Support: https://vercel.com/docs
- OpenAI Support: https://help.openai.com
- Anthropic Support: https://docs.anthropic.com

### Common Issues
1. CORS errors: Check CORS_ORIGINS includes Vercel domain
2. WebSocket connection fails: Verify wss:// protocol
3. API key errors: Check keys are set in Render dashboard
4. Build failures: Check logs for specific errors
5. Rate limiting: Adjust RATE_LIMIT_REQUESTS if needed

## Sign-off

Deployment completed by: ___________________
Date: ___________________
Production URLs verified: ___________________
Monitoring configured: ___________________
Team notified: ___________________
