"""Single place for branding and deploy settings."""
import os

BRAND = os.environ.get("LR_BRAND", "Layoff Tracker")
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")
