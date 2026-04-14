# Replit Deployment Guide for NYC Soccer Hub

This guide provides step-by-step instructions for deploying the site on Replit.

---

## Prerequisites

1. **Replit Account**: Sign up at https://replit.com
2. **API Keys**: 
   - Pexels API key: https://www.pexels.com/api/
   - Pixabay API key: https://pixabay.com/api/docs/

---

## Step 1: Import Project to Replit

### Option A: Import from GitHub
1. Create a new Repl
2. Choose "Import from GitHub"
3. Enter your repository URL
4. Select Python as the language

### Option B: Upload Files
1. Create a new Repl
2. Choose "Python" as the language
3. Upload all project files using the file uploader

---

## Step 2: Configure Environment Variables in Replit

**⚠️ CRITICAL: Set these before running the generator**

1. **Open Secrets Tab**:
   - Click on the "Secrets" tab (🔒 icon) in the left sidebar
   - Or use: Tools → Secrets

2. **Add Required Secrets**:
   Click "New secret" and add each of these:

   ```
   Key: PEXELS_API_KEY
   Value: your-actual-pexels-api-key
   ```

   ```
   Key: PIXABAY_API_KEY
   Value: your-actual-pixabay-api-key
   ```

   ```
   Key: BASE_URL
   Value: https://your-repl-name.your-username.repl.co
   ```
   *(Replace with your actual Replit URL)*

   ```
   Key: ENV
   Value: production
   ```

   ```
   Key: SECRET_KEY
   Value: [generate a strong random string]
   ```
   *(Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`)*

   ```
   Key: ALLOWED_ORIGINS
   Value: https://your-repl-name.your-username.repl.co
   ```
   *(Replace with your actual Replit URL)*

3. **Verify Secrets**:
   - All secrets should show as "Set" (not the actual values)
   - Secrets are automatically available as environment variables

---

## Step 3: Install Dependencies

1. **Open Shell** (Terminal tab)

2. **Install Python packages**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify installation**:
   ```bash
   python --version
   pip list
   ```

---

## Step 4: Generate the Site

1. **Run the generator**:
   ```bash
   python generate.py
   ```

2. **Expected output**:
   - "Starting site generation..."
   - "Loaded cache with X entries"
   - "Generating X pages..."
   - "Site generation complete!"

3. **Verify generation**:
   - Check that `public/` directory contains generated HTML files
   - Should see ~1,980 pages generated

---

## Step 5: Configure Replit for Static Site Hosting

### Option A: Use Replit Webview (Simple)

1. **Create `.replit` file** (if not exists):
   ```toml
   run = "python serve.py"
   ```

2. **Update `serve.py`** (if needed) to serve from `public/` directory

3. **Run the server**:
   - Click "Run" button
   - Site will be available at your Replit URL

### Option B: Use Replit Web Server (Recommended)

1. **Create `replit.nix`** (optional, for package management):
   ```nix
   { pkgs }: {
     deps = [
       pkgs.python38Full
       pkgs.python38Packages.pip
     ];
   }
   ```

2. **Create `.replit` file**:
   ```toml
   run = "python serve.py"
   language = "python3"
   
   [deploy]
   run = ["python", "serve.py"]
   ```

3. **Update `serve.py`** to serve static files:
   ```python
   from flask import Flask, send_from_directory
   import os
   
   app = Flask(__name__, static_folder='public', static_url_path='')
   
   @app.route('/')
   def index():
       return send_from_directory('public', 'uk/volleyball/index.html')
   
   @app.route('/<path:path>')
   def serve_static(path):
       return send_from_directory('public', path)
   
   if __name__ == '__main__':
       port = int(os.environ.get('PORT', 8080))
       app.run(host='0.0.0.0', port=port, debug=False)
   ```

---

## Step 6: Deploy and Configure Webview

1. **Enable Webview**:
   - Click the "Webview" tab
   - Or use: Tools → Webview

2. **Set Webview URL**:
   - Should automatically detect your Flask server
   - Or manually set to: `http://localhost:8080`

3. **Make Public** (Optional):
   - Click "Share" button
   - Copy the public URL
   - Update `BASE_URL` and `ALLOWED_ORIGINS` secrets with this URL

---

## Step 7: Automated Deployment (Optional)

### Create `.replit` with Auto-Deploy:

```toml
run = "python generate.py && python serve.py"
language = "python3"

[deploy]
run = ["sh", "-c", "python generate.py && python serve.py"]

[env]
PYTHONUNBUFFERED = "1"
```

### Or Create a Deployment Script:

**Create `deploy.sh`**:
```bash
#!/bin/bash
echo "Generating site..."
python generate.py

echo "Starting server..."
python serve.py
```

**Make executable**:
```bash
chmod +x deploy.sh
```

**Update `.replit`**:
```toml
run = "./deploy.sh"
```

---

## Step 8: Update serve.py for Replit

**Recommended `serve.py` for Replit**:

```python
#!/usr/bin/env python3
"""
Static file server for Replit deployment
Serves the generated static site from public/ directory
"""
from flask import Flask, send_from_directory, send_file
from pathlib import Path
import os

app = Flask(__name__)

# Serve from public directory
PUBLIC_DIR = Path("public")

@app.route('/')
def index():
    """Serve hub page"""
    return send_file(PUBLIC_DIR / "uk" / "volleyball" / "index.html")

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    file_path = PUBLIC_DIR / path
    
    # Check if it's a directory, serve index.html
    if file_path.is_dir():
        index_file = file_path / "index.html"
        if index_file.exists():
            return send_file(index_file)
        return "Directory not found", 404
    
    # Check if file exists
    if file_path.exists() and file_path.is_file():
        return send_file(file_path)
    
    # Try with index.html for directory paths
    if not path.endswith('.html'):
        html_path = PUBLIC_DIR / path / "index.html"
        if html_path.exists():
            return send_file(html_path)
    
    return "File not found", 404

@app.route('/robots.txt')
def robots():
    """Serve robots.txt"""
    return send_file(PUBLIC_DIR / "robots.txt")

@app.route('/sitemap.xml')
def sitemap():
    """Serve sitemap.xml"""
    return send_file(PUBLIC_DIR / "sitemap.xml"), 200, {'Content-Type': 'application/xml'}

if __name__ == '__main__':
    # Replit uses PORT environment variable
    port = int(os.environ.get('PORT', 8080))
    host = os.environ.get('HOST', '0.0.0.0')
    
    print(f"Starting server on {host}:{port}")
    print(f"Serving from: {PUBLIC_DIR.absolute()}")
    
    app.run(host=host, port=port, debug=False)
```

---

## Step 9: Verify Deployment

1. **Check Site Generation**:
   ```bash
   ls -la public/uk/volleyball/ | head -20
   ```

2. **Test Server**:
   - Click "Run" button
   - Check Webview tab
   - Verify pages load correctly

3. **Test Key Pages**:
   - Hub page: `/`
   - City page: `/uk/volleyball/london/`
   - Area page: `/uk/volleyball/london/central-london/`
   - Blog post: `/uk/volleyball/blog/...`

4. **Check Console**:
   - Look for any errors in the console
   - Verify all pages generate successfully

---

## Step 10: Re-Generate on Updates

When you need to regenerate the site:

1. **Update content/config** (if needed)

2. **Re-run generator**:
   ```bash
   python generate.py
   ```

3. **Restart server**:
   - Stop the current run (if running)
   - Click "Run" again

---

## Troubleshooting

### Issue: "Missing Required Environment Variables"
**Solution**: 
- Check Secrets tab - all required secrets must be set
- Verify secret names match exactly (case-sensitive)
- Restart Repl after adding secrets

### Issue: "API calls failing"
**Solution**:
- Verify API keys are correct in Secrets
- Check API key quotas haven't been exceeded
- Verify network connectivity

### Issue: "Pages not loading"
**Solution**:
- Verify `public/` directory exists and has files
- Check `serve.py` is serving from correct directory
- Verify file paths in routes match actual structure

### Issue: "CORS errors"
**Solution**:
- Update `ALLOWED_ORIGINS` secret with your Replit URL
- Format: `https://your-repl-name.your-username.repl.co`
- Restart server after updating

### Issue: "Port already in use"
**Solution**:
- Replit automatically handles PORT - don't hardcode it
- Use `os.environ.get('PORT', 8080)` in serve.py

---

## Replit-Specific Optimizations

### 1. Use Replit Database (Optional)
If you need to store leads/data:
- Use Replit Database instead of SQLite
- More reliable for persistent storage

### 2. Scheduled Regeneration
Use Replit's Always On feature:
- Keeps your site running 24/7
- Can set up cron jobs for automatic regeneration

### 3. Custom Domain (Pro Feature)
- Replit Pro allows custom domains
- Update `BASE_URL` and `ALLOWED_ORIGINS` with custom domain

---

## Quick Start Checklist

- [ ] Project imported/uploaded to Replit
- [ ] All secrets configured (PEXELS_API_KEY, PIXABAY_API_KEY, etc.)
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Site generated (`python generate.py`)
- [ ] `serve.py` updated for Replit
- [ ] Server running and accessible via Webview
- [ ] Tested key pages (hub, city, area, blog)
- [ ] No errors in console

---

## Replit Secrets Checklist

Set these in Replit **Secrets** (Tools → Secrets) before running:

| Secret Name | Required | Example Value |
|-------------|----------|---------------|
| `PEXELS_API_KEY` | ✅ Yes (for generation) | `your-pexels-key` |
| `PIXABAY_API_KEY` | ✅ Yes (for generation) | `your-pixabay-key` |
| `BASE_URL` | ✅ Yes | `https://your-repl.repl.co` |
| `ENV` | ⚠️ Recommended | `production` |
| `SECRET_KEY` | ✅ Yes (if using API) | Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `ALLOWED_ORIGINS` | ✅ Yes (if using API) | `https://your-repl.repl.co` (must not be `*` in production) |
| `ADMIN_PASSWORD_HASH` | Optional (for admin panel) | Werkzeug hash; or create `api/config.py` from `api/config.py.example` |
| `SKIP_GENERATION` | Optional | `1` to skip running the generator when `public/` already exists (faster restarts) |

---

## Database persistence (leads)

Leads from the sign-up forms are stored in **SQLite** (`api/leads.db` by default). On Replit, the filesystem is **ephemeral**: repl restarts can wipe the database. For production:

- Either accept that leads may be lost on restart, or
- Use Replit Database or an external database and point the app at it via configuration (keep DB config env-driven).

Admin login requires `ADMIN_PASSWORD_HASH` to be set (in `api/config.py` or via the `ADMIN_PASSWORD_HASH` secret). See `api/config.py.example` for generating a hash.

---

## Optional: Skip generation on run (SKIP_GENERATION)

By default, the run command runs `python generate.py && python serve_replit.py`, so every start regenerates the site. To **skip generation** when the site is already built (e.g. after a one-off build or when using persistent storage):

1. Set secret: `SKIP_GENERATION` = `1`
2. Ensure `public/index.html` (or your hub path) already exists from a previous run or build.

Then "Run" will skip the generator and start the server only, reducing cold-start time.

---

## Support

If you encounter issues:
1. Check Replit console for error messages
2. Verify all secrets are set correctly
3. Ensure `public/` directory has generated files
4. Check `serve.py` is configured correctly

---

**Last Updated:** 2025-12-26  
**Replit Version:** Current as of deployment date

