# NYC Soccer Hub

## Overview
Static site generator for NYC Soccer Hub - a platform to find and organize pickup soccer games across NYC and Long Island. Built with Python, generates ~214 static HTML pages served via Flask. Leads are stored in PostgreSQL with a built-in admin console.

## Recent Changes
- 2026-02-18: Migrated from SQLite to PostgreSQL (Neon-backed) for lead storage and admin console
- 2026-02-18: Admin console accessible at /admin (password-protected dashboard with lead filtering, stats, referral tracking)
- 2026-02-18: Form submissions go to /api/notify endpoint (stored in PostgreSQL, not Google Sheets)
- 2026-02-18: Set up SECRET_KEY and ADMIN_PASSWORD_HASH secrets for session management
- 2026-02-10: Set production BASE_URL to https://nycsoccerhub.com, split env vars by environment (dev vs prod)
- 2026-02-10: Fixed referral link container overflow (CSS), fixed organizer checkbox form submission (JS)
- 2026-02-10: Renamed images/videos to clean filenames, configured favicon and navbar logo
- 2026-02-10: Initial Replit setup - installed Python 3.12, Flask dependencies, configured port 5000

## Project Architecture
- **Generator**: `generate.py` (4,166 lines) - Static site generator with parallel processing, API caching, and error recovery
- **Server**: `serve_replit.py` - Flask server serving static files from `public/` with API routes
- **API**: `api/` - Flask blueprints for form submissions, admin panel, media, referrals
- **Database**: PostgreSQL (Neon-backed) - leads, referral_codes, referrals, user_badges tables
- **Admin Console**: `/admin` - Password-protected dashboard for lead management
- **Config**: `src/config/` - JSON-based configuration (site.config.json, nyc-sport.config.json)
- **Output**: `public/` - Generated static HTML files (not in git)

## Key Files
- `generate.py` - Main site generator (parallel processing, media API integration)
- `serve_replit.py` - Flask server (port 5000, serves public/ directory + API + admin)
- `api/models/database.py` - Database models (PostgreSQL/SQLite dual support)
- `api/routes/admin.py` - Admin dashboard routes (/admin, /admin/login, /admin/dashboard)
- `api/routes/notify.py` - Lead submission endpoint (/api/notify)
- `api/templates/admin.html` - Admin dashboard template
- `src/config/config_loader.py` - Configuration loader with env overrides
- `api/utils/config.py` - API configuration (CORS, rate limits, DATABASE_URL)

## Environment Variables
- `DATABASE_URL` - PostgreSQL connection string (auto-set by Replit)
- `SECRET_KEY` - Required for API sessions (secret)
- `ADMIN_PASSWORD_HASH` - Hashed admin password for dashboard login (secret)
- `PEXELS_API_KEY` - Required for media fetching during site generation (secret)
- `PIXABAY_API_KEY` - Required for media fetching during site generation (secret)
- `BASE_URL` - Site base URL (dev: Replit dev domain, prod: https://nycsoccerhub.com)
- `ENV` - Environment mode: production/development (env var)
- `ALLOWED_ORIGINS` - CORS allowed origins (dev: Replit dev domain, prod: https://nycsoccerhub.com)
- `SKIP_GENERATION` - Set to 1 to skip regeneration when public/ exists

## Database Schema
- **leads** - Email, city, name, phone, skill_level, organizer_interest, preferred_times, page_url, utm_json, referral tracking
- **referral_codes** - User email to referral code mapping
- **referrals** - Referrer/referee tracking with status
- **user_badges** - Badge system for referral milestones

## Admin Console
- URL: /admin (login page) -> /admin/dashboard
- Default password: admin123 (change via ADMIN_PASSWORD_HASH secret)
- Features: Lead filtering (city, organizer interest, date range), pagination, stats (total members, organizers, by city, daily/weekly/WoW trends)

## Deployment
- Production URL: https://nycsoccerhub.com
- Deploy target: autoscale
- Build step: `python generate.py` (regenerates site with production BASE_URL)
- Run: `python serve_replit.py`

## How to Run
1. Set required secrets (SECRET_KEY, ADMIN_PASSWORD_HASH, DATABASE_URL auto-provided)
2. Run `python generate.py` to generate the static site (needs PEXELS/PIXABAY keys)
3. Run `SKIP_GENERATION=1 python serve_replit.py` to serve on port 5000 (skips regeneration)

## User Preferences
- Admin console should be at /admin (not /api/admin)
