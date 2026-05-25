import os

from dotenv import load_dotenv

load_dotenv()

APP_TITLE = "Duplom Flight API (SerpApi + DB daily snapshots)"
APP_VERSION = "0.7.0"

SERPAPI_URL = "https://serpapi.com/search.json"
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
AUTH_SESSION_TTL_HOURS = int(os.getenv("AUTH_SESSION_TTL_HOURS", "168"))
