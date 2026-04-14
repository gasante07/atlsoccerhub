# Server Setup Guide

## ⚠️ Important: Port 5500 vs API Server

The error `POST http://127.0.0.1:5500/api/notify 405 (Method Not Allowed)` indicates you're using a **static file server** (like Live Server, VS Code's Live Server, or Python's http.server) on port 5500.

**These static servers CANNOT handle API requests** - they only serve files.

## ✅ Solution: Use the Flask Server

You need to run the Flask server that includes API routes:

### Option 1: Use serve_replit.py (Recommended)

```bash
python serve_replit.py
```

This will:
- Serve static files from `public/` directory
- Handle API routes (`/api/notify`, etc.)
- Run on port 8080 (or PORT environment variable)

Then access your site at: `http://localhost:8080`

### Option 2: Use api/app.py (Development)

```bash
python api/app.py
```

This runs the API server on port 5000. You'll need to:
- Serve static files separately, OR
- Use `serve_replit.py` which combines both

## 🔧 Quick Fix Steps

1. **Stop your current server** (the one on port 5500)

2. **Start the Flask server:**
   ```bash
   python serve_replit.py
   ```

3. **Access your site at:**
   ```
   http://localhost:8080
   ```
   (or whatever port it shows in the console)

4. **Test the form** - it should work now!

## 📋 Port Configuration

- **serve_replit.py**: Uses `PORT` environment variable (default: 8080)
- **api/app.py**: Runs on port 5000
- **Static servers** (Live Server, etc.): Usually port 5500 or 3000

## 🐛 Troubleshooting

### Still getting 405 error?

1. **Check which server is running:**
   ```bash
   # Windows
   netstat -ano | findstr :5500
   netstat -ano | findstr :8080
   ```

2. **Make sure serve_replit.py is running:**
   - You should see: `✅ API routes registered`
   - Check console output

3. **Verify API routes are loaded:**
   - Visit: `http://localhost:8080/health`
   - Should return JSON with status

### API routes not registering?

1. **Check dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Check for import errors:**
   - Look at server console output
   - Should not see any ImportError messages

3. **Verify file structure:**
   - `api/` directory exists
   - `api/routes/notify.py` exists
   - `api/utils/` directory exists

## 💡 Development Workflow

### Recommended Setup:

1. **Generate pages:**
   ```bash
   python generate.py
   ```

2. **Start server:**
   ```bash
   python serve_replit.py
   ```

3. **Access site:**
   ```
   http://localhost:8080
   ```

### For Replit Deployment:

The `.replit` file is configured to run:
```bash
python generate.py && python serve_replit.py
```

This automatically:
- Generates pages
- Starts server with API routes
- Ready for deployment

## 📝 Notes

- **Port 5500** = Static file server (no API support)
- **Port 8080** = Flask server with API routes (use this!)
- The form submission **requires** the Flask server with API routes
- Static file servers cannot handle POST requests to `/api/notify`
