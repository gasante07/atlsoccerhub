# Deployment Security Guide

## Critical Security Checklist

Before deploying to production, ensure all security measures are in place:

### ✅ 1. API Keys (REQUIRED)

**Status:** ✅ Fixed - API keys now require environment variables

**Action Required:**
1. Set the following environment variables in your production environment:
   ```bash
   export PEXELS_API_KEY='your-actual-pexels-key'
   export PIXABAY_API_KEY='your-actual-pixabay-key'
   ```

2. **Never commit API keys to version control**
3. Use your hosting platform's environment variable management:
   - **Vercel/Netlify**: Set in project settings → Environment Variables
   - **AWS**: Use AWS Secrets Manager or Parameter Store
   - **Docker**: Use docker-compose with .env file (not in repo)
   - **Heroku**: Use `heroku config:set PEXELS_API_KEY=xxx`

### ✅ 2. CORS Configuration (REQUIRED)

**Status:** ✅ Fixed - CORS now uses environment variable

**Action Required:**
1. Set `ALLOWED_ORIGINS` environment variable in production:
   ```bash
   export ALLOWED_ORIGINS='https://volleyballhub.uk'
   ```

2. For multiple domains (if needed):
   ```bash
   export ALLOWED_ORIGINS='https://volleyballhub.uk,https://www.volleyballhub.uk'
   ```

3. **Never use `["*"]` in production** - this allows any origin to access your API

### ✅ 3. Secret Key (REQUIRED)

**Status:** ⚠️ Needs Production Value

**Action Required:**
1. Generate a strong random secret key:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Set in production environment:
   ```bash
   export SECRET_KEY='your-generated-secret-key'
   ```

3. **Never use default "dev-secret-key-change-in-production" in production**

### ✅ 4. Admin Password (REQUIRED for API)

**Action Required:**
1. Generate password hash:
   ```python
   from werkzeug.security import generate_password_hash
   print(generate_password_hash('your-strong-password'))
   ```

2. Add to `api/config.py`:
   ```python
   ADMIN_PASSWORD_HASH = "pbkdf2:sha256:600000$..."
   ```

3. **Never commit `api/config.py` to version control** - add to `.gitignore`

---

## Environment Variables Summary

### For Site Generation (Static Site)
```bash
PEXELS_API_KEY=required
PIXABAY_API_KEY=required
BASE_URL=optional (defaults to https://volleyballhub.uk)
ENV=optional (development/staging/production)
```

### For API Server
```bash
SECRET_KEY=required
ALLOWED_ORIGINS=required (set to production domain)
DATABASE_PATH=optional (defaults to api/leads.db)
RATE_LIMIT_PER_HOUR=optional (defaults to 5)
RATE_LIMIT_PER_DAY=optional (defaults to 20)
ADMIN_PASSWORD_HASH=required (set in api/config.py, not env var)
```

---

## Pre-Deployment Checklist

- [ ] All API keys set as environment variables (not in code)
- [ ] CORS restricted to production domain
- [ ] Strong secret key generated and set
- [ ] Admin password hash generated and set in api/config.py
- [ ] `api/config.py` added to `.gitignore`
- [ ] `.env` file added to `.gitignore` (if using)
- [ ] HTTPS enabled on all URLs
- [ ] Test API endpoints with production CORS settings
- [ ] Verify no API keys in git history (use `git-secrets` or similar)

---

## Security Best Practices

1. **Never commit secrets**: Use `.gitignore` for config files with secrets
2. **Rotate keys regularly**: Change API keys periodically
3. **Use different keys**: Separate keys for dev/staging/production
4. **Monitor usage**: Check API usage logs for suspicious activity
5. **Limit access**: Only grant API access to necessary services
6. **Use HTTPS**: Always use HTTPS in production
7. **Rate limiting**: API has rate limiting - ensure it's configured appropriately

---

## Quick Start for Production

1. **Set environment variables:**
   ```bash
   export PEXELS_API_KEY='your-key'
   export PIXABAY_API_KEY='your-key'
   export SECRET_KEY='your-secret-key'
   export ALLOWED_ORIGINS='https://volleyballhub.uk'
   export ENV='production'
   ```

2. **Generate site:**
   ```bash
   python generate.py
   ```

3. **Deploy static files** from `public/` directory

4. **Deploy API** (if using) with environment variables set

---

## Troubleshooting

### "Missing Required Environment Variables" Error
- Ensure all required environment variables are set
- Check that variables are exported in your shell/environment
- Verify variable names are correct (case-sensitive)

### API Calls Failing
- Verify API keys are valid and have not expired
- Check API rate limits haven't been exceeded
- Ensure network connectivity to API endpoints

### CORS Errors
- Verify `ALLOWED_ORIGINS` includes your frontend domain
- Check that domain matches exactly (including https://)
- Ensure no trailing slashes in domain

---

**Last Updated:** 2025-12-26

