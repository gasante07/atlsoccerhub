# Deployment Quick Start Guide

## 🚨 CRITICAL: Before You Start

**IMPORTANT:** The API keys in `ENV_EXAMPLE.txt` have been sanitized. You MUST:
1. Get your own API keys from:
   - Pexels: https://www.pexels.com/api/
   - Pixabay: https://pixabay.com/api/docs/
2. Set them as environment variables (never commit them to git)

---

## GitHub Deployment Checklist

### 1. Pre-Commit Checks

```bash
# Ensure no sensitive data is committed
git status
git diff

# Verify .gitignore is working
git check-ignore api/config.py .env
# Should output: api/config.py and .env

# Check for any exposed secrets
grep -r "api[_-]key\s*=" --include="*.py" --include="*.txt" .
# Should only show placeholder values
```

### 2. Create .env File (Local Development Only)

```bash
# Copy the example file
cp ENV_EXAMPLE.txt .env

# Edit .env and add your actual API keys
# NEVER commit .env to git!
```

### 3. Set Up API Configuration

```bash
# Copy API config template
cp api/config.py.example api/config.py

# Generate admin password hash
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your-strong-password'))"

# Edit api/config.py and add:
# - ADMIN_PASSWORD_HASH (from above)
# - SECRET_KEY (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
```

### 4. Test Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Test site generation
python generate.py

# Test API server
python api/app.py
# Visit http://localhost:5000/health
```

### 5. Commit and Push

```bash
# Stage changes
git add .

# Commit (with meaningful message)
git commit -m "Prepare for deployment: fix security issues and add CI/CD"

# Push to GitHub
git push origin main
```

---

## Replit Deployment Checklist

### 1. Import to Replit

1. Create new Repl
2. Choose "Import from GitHub"
3. Enter your repository URL
4. Select Python as language

### 2. Set Environment Variables (Secrets)

**CRITICAL:** Set these in Replit Secrets tab (🔒 icon):

```
PEXELS_API_KEY=your-actual-pexels-key
PIXABAY_API_KEY=your-actual-pixabay-key
BASE_URL=https://your-repl-name.username.repl.co
ENV=production
SECRET_KEY=your-generated-secret-key
ALLOWED_ORIGINS=https://your-repl-name.username.repl.co
FLASK_DEBUG=false
```

**Generate SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Configure API (if using API endpoints)

1. Open Shell in Replit
2. Run:
```bash
cp api/config.py.example api/config.py
```

3. Edit `api/config.py`:
   - Add `ADMIN_PASSWORD_HASH` (generate with Python command above)
   - Add `SECRET_KEY` (same as environment variable)
   - Set `ALLOWED_ORIGINS` to your Replit URL

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Generate Site

```bash
python generate.py
```

This will:
- Fetch media from APIs
- Generate all HTML pages
- Create sitemap.xml and robots.txt
- Copy static assets

### 6. Run Server

The `.replit` file is configured to run:
```bash
python generate.py && python serve_replit.py
```

Or manually:
```bash
python serve_replit.py
```

### 7. Verify Deployment

1. Visit your Replit URL
2. Check health endpoint: `https://your-repl.repl.co/health`
3. Test API endpoints (if using API)
4. Verify static files are served correctly

---

## Post-Deployment Verification

### Security Checks

- [ ] No API keys in git history
- [ ] Debug mode disabled
- [ ] SECRET_KEY is not default value
- [ ] CORS is restricted to your domain
- [ ] Admin password is set
- [ ] HTTPS is enabled

### Functionality Checks

- [ ] Site generates successfully
- [ ] All pages load correctly
- [ ] API endpoints respond
- [ ] Database operations work
- [ ] Forms submit successfully
- [ ] Admin panel accessible
- [ ] Health check returns 200

### Performance Checks

- [ ] Page load times < 3 seconds
- [ ] API response times < 500ms
- [ ] No memory leaks
- [ ] Database queries optimized

---

## Troubleshooting

### Site Generation Fails

**Error:** Missing API keys
```bash
# Check environment variables
echo $PEXELS_API_KEY
echo $PIXABAY_API_KEY

# Set if missing
export PEXELS_API_KEY=your-key
export PIXABAY_API_KEY=your-key
```

### API Server Won't Start

**Error:** Secret key validation failed
```bash
# Generate new secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set in environment
export SECRET_KEY=your-generated-key
```

**Error:** Database not found
```bash
# Database will be created automatically on first run
# Ensure api/ directory is writable
```

### Pages Not Loading

**Check:**
1. Site was generated: `ls public/uk/football/`
2. Server is serving from correct directory
3. File permissions are correct
4. Base path matches configuration

---

## Monitoring

### Health Check Endpoint

```bash
curl https://your-site.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2026-01-27T12:00:00",
  "service": "NYC Soccer Hub API"
}
```

### Logs

Check Replit logs for:
- API errors
- Database errors
- Rate limiting issues
- Performance warnings

---

## Rollback Plan

If deployment fails:

1. **Revert Git Commit:**
```bash
git revert HEAD
git push origin main
```

2. **Restore Previous Environment Variables:**
   - Update Replit Secrets to previous values

3. **Regenerate Site:**
```bash
python generate.py
```

---

## Support

For issues:
1. Check `DEPLOYMENT_READINESS_AUDIT.md` for known issues
2. Review error logs
3. Verify environment variables
4. Test locally first

---

## Next Steps

After successful deployment:
1. Set up monitoring/alerting
2. Configure backups
3. Set up CI/CD for automated deployments
4. Add performance monitoring
5. Review security regularly
