"""SQLite storage. Items are raw fetched documents; claims/events are recomputed every run."""
import sqlite3

from .util import DATA

SCHEMA = """
CREATE TABLE IF NOT EXISTS items(
  id INTEGER PRIMARY KEY,
  uid TEXT UNIQUE,            -- stable id: source + url/notice key
  source TEXT,                -- gnews | edgar | warn_ca | warn_md | hn | reddit
  tier TEXT,                  -- official | major | news | aggregator | social
  publisher TEXT,
  url TEXT,
  title TEXT,
  text TEXT,
  published TEXT,             -- ISO date
  fetched_at TEXT,
  meta TEXT                   -- JSON: structured fields from official sources
);
CREATE TABLE IF NOT EXISTS claims(
  id INTEGER PRIMARY KEY,
  item_id INTEGER REFERENCES items(id),
  company TEXT, slug TEXT,
  headcount INTEGER, pct REAL,
  kind TEXT,                  -- layoff | closure | buyout
  date TEXT, country TEXT, location TEXT, industry TEXT,
  weight REAL, speculative INTEGER DEFAULT 0, method TEXT
);
CREATE INDEX IF NOT EXISTS claims_slug ON claims(slug);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY,
  slug TEXT, company TEXT,
  start TEXT, end TEXT,
  headcount INTEGER, low INTEGER, high INTEGER, pct REAL,
  confidence INTEGER, label TEXT,
  industry TEXT, country TEXT,
  n_sources INTEGER, n_publishers INTEGER, has_official INTEGER,
  kind TEXT, headline TEXT, visible INTEGER
);
CREATE TABLE IF NOT EXISTS event_claims(event_id INTEGER, claim_id INTEGER);
CREATE TABLE IF NOT EXISTS geo(place TEXT PRIMARY KEY, lat REAL, lon REAL);
CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, at TEXT, stats TEXT);
"""


def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DATA / "radar.db")
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con
