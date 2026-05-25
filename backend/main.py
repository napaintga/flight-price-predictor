from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core import APP_TITLE, APP_VERSION
from db.ops import _ensure_db
from routes import router

app = FastAPI(title=APP_TITLE, version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def _startup() -> None:
    _ensure_db()

app.include_router(router)
