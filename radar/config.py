"""Single place for branding and deploy settings. The product name is still a placeholder."""
import os

BRAND = os.environ.get("LR_BRAND", "layoff-radar")
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")
