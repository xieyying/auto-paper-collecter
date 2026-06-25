"""FastAPI entrypoint. Serves the API + the static dashboard, starts the scheduler."""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .db import Base, engine
from . import models  # noqa: F401  (register tables)
from .api import router
from .scheduler import start_scheduler

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ScholarPulse API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def _startup():
    start_scheduler()


@app.get("/health")
def health():
    return {"ok": True}


# serve the dashboard (frontend/) at root, if present
_static = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(_static):
    app.mount("/", StaticFiles(directory=_static, html=True), name="static")
