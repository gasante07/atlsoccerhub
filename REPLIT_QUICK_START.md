# Replit Quick Start Guide

## 🚀 5-Minute Setup

### Step 1: Import to Replit
1. Create new Repl
2. Choose "Python" language
3. Upload your project files

### Step 2: Set Secrets (🔒 Tab)
Add these secrets (Tools → Secrets). See **REPLIT_DEPLOYMENT_GUIDE.md** for the full Replit Secrets checklist.

```
PEXELS_API_KEY = your-pexels-key
PIXABAY_API_KEY = your-pixabay-key
BASE_URL = https://your-repl-name.your-username.repl.co
ENV = production
SECRET_KEY = [generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"]
ALLOWED_ORIGINS = https://your-repl-name.your-username.repl.co
```
Optional: `ADMIN_PASSWORD_HASH` (for admin panel); `SKIP_GENERATION=1` (skip generator when site already built).

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Generate & Run
Click **"Run"** button - it will:
1. Generate all pages (takes ~5-10 seconds)
2. Start the server automatically

### Step 5: View Site
- Click **"Webview"** tab
- Your site is live! 🎉

---

## 📝 Files for Replit

- **`.replit`** - Auto-configures run command
- **`serve_replit.py`** - Optimized Flask server for Replit
- **`REPLIT_DEPLOYMENT_GUIDE.md`** - Full detailed guide

---

## ⚠️ Important Notes

1. **First Run**: Takes longer (generates 1,980 pages)
2. **Secrets**: Must be set before first run (including `ALLOWED_ORIGINS` — cannot be `*` in production)
3. **Webview**: Enable in Tools → Webview
4. **Updates**: Just click "Run" again to regenerate (or set `SKIP_GENERATION=1` to skip generation when `public/` already exists)
5. **Leads DB**: Stored in SQLite; on Replit the filesystem is ephemeral so leads may be lost on restart unless you use persistent storage or Replit Database

---

## 🔧 Troubleshooting

**"Missing API keys"** → Check Secrets tab
**"Pages not loading"** → Wait for generation to complete
**"Port in use"** → Replit handles this automatically

---

**That's it!** Your site should be live on Replit. 🎊

