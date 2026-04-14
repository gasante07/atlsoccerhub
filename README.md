# NYC Soccer Hub – Pickup Soccer in NYC and Long Island

A programmatic, SEO-optimized microsite for finding, organizing, and playing pickup soccer across NYC and Long Island. Built with static site generation, Python backend, and a clean, modern design.

## Features

- **Community Building**: Helps people find, organize, and play pickup soccer across NYC’s five boroughs and Long Island (Nassau & Suffolk)
- **Game Discovery**: Discover games by borough and neighborhood (Manhattan, Brooklyn, Queens, Bronx, Staten Island, Nassau County, Suffolk County)
- **Player Matching**: Meet players of all skill levels
- **Notifications**: Get notified when new games go live
- **Organizer Support**: Organize games and build your own community
- **SEO Optimized**: Pre-rendered pages, structured data, comprehensive FAQs
- **Mobile-First**: Optimized for mobile, iPad, and desktop
- **Scalable**: Add or edit areas by updating `src/config/nyc-sport.config.json` (no code changes required)

## Project Structure

```
/
├── src/
│   ├── config/          # Configuration files
│   ├── templates/       # HTML templates
│   ├── styles/          # CSS files
│   ├── js/              # JavaScript files
│   └── utils/           # Utility scripts (Pexels API)
├── api/                 # Python backend (Flask)
├── public/              # Generated static files (deploy this)
├── generate.js          # Static site generator
└── README.md
```

## Setup

### Prerequisites

- Python 3.8+ (for site generation and backend API)
- Pexels API key (get from https://www.pexels.com/api/)
- Pixabay API key (get from https://pixabay.com/api/docs/)

### Installation

1. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables** (REQUIRED):
   ```bash
   # Copy the example file
   cp ENV_EXAMPLE.txt .env
   
   # Edit .env and add your API keys:
   export PEXELS_API_KEY='your-pexels-api-key'
   export PIXABAY_API_KEY='your-pixabay-api-key'
   export BASE_URL='https://soccernyc.com'
   export ENV='production'
   ```

   **⚠️ Security Note:** Never commit `.env` to version control. API keys must be set as environment variables.

3. **Configure Python backend** (if using API):
   ```bash
   cp api/config.py.example api/config.py
   # Edit api/config.py with your settings
   # Generate admin password hash:
   python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your_password'))"
   ```

### Build

Generate static pages:
```bash
python generate.py
```

This will:
- Fetch media from Pexels/Pixabay APIs
- Generate HTML pages for each area (boroughs + Long Island) and their neighborhoods
- Generate blog posts
- Generate sitemap.xml and robots.txt
- Copy static assets to `/public`

**Adding or editing areas:** Edit `src/config/nyc-sport.config.json`. Add or change entries under `cities` (each with a `name`, `slug`, and `areas` array of neighborhoods/towns). Re-run `python generate.py`.

**Note:** The generator requires `PEXELS_API_KEY` and `PIXABAY_API_KEY` environment variables to be set.

### Run the site locally

The landing page is at **root** (`/`). Serve the **`public`** folder so that `/` shows it (otherwise you may see a directory listing).

**Option A – Use the project server (recommended)**  
From the project root (`Footballhub_uk`):

```bash
python serve.py
```

This serves the `public` folder at **http://127.0.0.1:5500/** . Open that URL to view the site. If port 5500 is in use, stop the other process or change `PORT` in `serve.py`.

**Option B – Live Server in Cursor/VS Code**  
1. In the file explorer, **right‑click the `public` folder** (not the project root).  
2. Choose **“Open with Live Server”** (or equivalent).  
The server root will be `public`, so **http://127.0.0.1:5500/** will load the landing page.

### Run Backend (Development)

```bash
python api/app.py
```

The API will run on `http://localhost:5000`

### Production Deployment

**⚠️ CRITICAL: Security Checklist Before Deployment**

See `DEPLOYMENT_SECURITY_GUIDE.md` for complete security checklist.

**Required Environment Variables:**
- `PEXELS_API_KEY` - Your Pexels API key
- `PIXABAY_API_KEY` - Your Pixabay API key
- `SECRET_KEY` - Strong random secret key (for API)
- `ALLOWED_ORIGINS` - Your production domain (e.g., `https://soccernyc.com`)

1. **Static Files**: Upload contents of `/public` to your web server/CDN
2. **Python API** (if using): Deploy using Gunicorn:
   ```bash
   gunicorn api.app:app
   ```
   Ensure all environment variables are set in your deployment environment.

**For detailed deployment instructions, see `DEPLOYMENT_SECURITY_GUIDE.md`**

### Deployment on Replit

- **Database:** When you add a Postgres resource in Replit, `DATABASE_URL` is set automatically. The API uses PostgreSQL when `DATABASE_URL` is set; otherwise it uses SQLite (`leads.db`). Production should use PostgreSQL so data survives restarts.
- **Admin console:** Access at **/admin** (login at `/admin`, dashboard at `/admin/dashboard`). Set `ADMIN_PASSWORD_HASH` in Replit Secrets to the hash of your admin password (e.g. run `python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('Brooklyn1'))"` and paste the result).
- **CSV export:** After logging in to admin, use the Export CSV button or **GET /api/export** (same session) to download leads. Export includes referral columns and returns all leads (no row limit).

## Configuration

### Site Configuration (`src/config/site.config.js`)

- Branding (site name, tagline)
- Base URL
- Pexels API key
- Form settings

### UK Sport Config (`src/config/uk-sport.config.json`)

- Cities list
- FAQ templates
- Answer block steps
- Quick facts

## API Endpoints

- `POST /api/notify` - Lead submission (form posts here when leads endpoint is empty)
- `GET /admin` - Admin login page
- `GET /admin/dashboard` - Admin dashboard (after login)
- `GET /api/export` - CSV export (requires admin session)

## Admin Access

1. Set `ADMIN_PASSWORD_HASH` in environment (or `api/config.py`) to the hash of your password.
2. Visit **/admin**
3. Log in with your password
4. View leads, filter by city/organizer, see stats (added today, this week, week over week), export CSV

## Design System

- **Colors**: Black, white, minimal grays (Nike.com style)
- **Typography**: Bold, large headlines (2.5rem - 6rem)
- **Layout**: Full-bleed hero sections, generous spacing
- **Responsive**: Mobile-first, optimized for all devices

## License

Powered by GameOn Active

