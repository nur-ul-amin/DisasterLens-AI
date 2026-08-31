"""
main.py — NDMA DisasterLens AI Backend
========================================
FastAPI application entry point.

v2.0 additions:
  - Async lifespan context: starts background news polling worker on startup
  - /api/v1/news router: GeoJSON map layers, paginated feed, worker status
  - All existing /api/v1/reports routes unchanged
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from news_aggregator.fetcher import background_polling_worker
from routes import news as news_router
from routes import reports

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("main")

# ─── Lifespan: Start/Stop Background Polling Worker ──────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
  """FastAPI lifespan context manager.

  Starts the 10-second news aggregation polling worker on startup. Cancels it
  cleanly on shutdown.
  """
  worker_task = None
  if not os.environ.get("VERCEL"):
    logger.info("[Startup] Launching news aggregation background worker...")
    worker_task = asyncio.create_task(background_polling_worker())

  yield  # Application runs here

  if worker_task:
    logger.info("[Shutdown] Cancelling news aggregation worker...")
    worker_task.cancel()
    try:
      await worker_task
    except asyncio.CancelledError:
      logger.info("[Shutdown] Worker stopped cleanly.")


# ─── FastAPI Application ──────────────────────────────────────────────────────

app = FastAPI(
    title="NDMA DisasterLens AI — Multi-Hazard Platform API",
    description=(
        "Pakistan National Disaster Management Authority — DisasterLens AI"
        " Command & Control Backend. Includes live disaster news aggregation,"
        " GeoJSON map layers, incident reporting, and trust-scored event"
        " clustering."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────

# Existing: Field incident reports from PWA & social media
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Field Reports"])

# New v2.0: Live disaster news aggregation subsystem
app.include_router(
    news_router.router, prefix="/api/v1/news", tags=["Live News Aggregation"]
)

# ─── Static File Serving ──────────────────────────────────────────────────────


@app.get("/", include_in_schema=False)
@app.get("/news_panel.html", include_in_schema=False)
def serve_news_panel():
  """Serve the Live News Panel HTML."""
  backend_path = os.path.join(os.path.dirname(__file__), "news_panel.html")
  pwa_path = os.path.join(
      os.path.dirname(__file__), "..", "resilientpath-pwa", "news_panel.html"
  )

  if os.path.exists(backend_path):
    return FileResponse(
        backend_path,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
  elif os.path.exists(pwa_path):
    return FileResponse(
        pwa_path,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
  return {"message": "News Panel UI not found."}


@app.get("/neoc_dashboard.html", include_in_schema=False)
@app.get("/legacy", include_in_schema=False)
def serve_legacy_dashboard():
  """Serve the legacy NEOC Dashboard HTML."""
  dashboard_path = os.path.join(os.path.dirname(__file__), "neoc_dashboard.html")
  if os.path.exists(dashboard_path):
    return FileResponse(
        dashboard_path,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
  return {"message": "Dashboard UI not found."}


@app.get("/news_panel.css", include_in_schema=False)
def serve_news_panel_css():
  """Serve news_panel.css."""
  backend_path = os.path.join(os.path.dirname(__file__), "news_panel.css")
  pwa_path = os.path.join(
      os.path.dirname(__file__), "..", "resilientpath-pwa", "news_panel.css"
  )
  if os.path.exists(backend_path):
    return FileResponse(backend_path, media_type="text/css")
  elif os.path.exists(pwa_path):
    return FileResponse(pwa_path, media_type="text/css")
  return {"detail": "news_panel.css missing"}


@app.get("/news_layer.js", include_in_schema=False)
def serve_news_layer_js():
  """Serve news_layer.js."""
  backend_path = os.path.join(os.path.dirname(__file__), "news_layer.js")
  pwa_path = os.path.join(
      os.path.dirname(__file__), "..", "resilientpath-pwa", "news_layer.js"
  )
  if os.path.exists(backend_path):
    return FileResponse(backend_path, media_type="application/javascript")
  elif os.path.exists(pwa_path):
    return FileResponse(pwa_path, media_type="application/javascript")
  return {"detail": "news_layer.js missing"}


@app.get("/style.css", include_in_schema=False)
def serve_style_css():
  """Serve style.css."""
  backend_path = os.path.join(os.path.dirname(__file__), "style.css")
  pwa_path = os.path.join(
      os.path.dirname(__file__), "..", "resilientpath-pwa", "style.css"
  )
  if os.path.exists(backend_path):
    return FileResponse(backend_path, media_type="text/css")
  elif os.path.exists(pwa_path):
    return FileResponse(pwa_path, media_type="text/css")
  return {"detail": "style.css missing"}


@app.get("/index.html", include_in_schema=False)
def serve_pwa_index():
  """Serve PWA field reporting interface."""
  pwa_index = os.path.join(os.path.dirname(__file__), "index.html")
  if os.path.exists(pwa_index):
    return FileResponse(pwa_index)
  return {"detail": "index.html missing"}


@app.get("/app.js", include_in_schema=False)
def serve_pwa_js():
  """Serve app.js."""
  pwa_js = os.path.join(os.path.dirname(__file__), "app.js")
  if os.path.exists(pwa_js):
    return FileResponse(pwa_js, media_type="application/javascript")
  return {"detail": "app.js missing"}


@app.get("/sw.js", include_in_schema=False)
def serve_pwa_sw():
  """Serve sw.js."""
  pwa_sw = os.path.join(os.path.dirname(__file__), "sw.js")
  if os.path.exists(pwa_sw):
    return FileResponse(pwa_sw, media_type="application/javascript")
  return {"detail": "sw.js missing"}


@app.get("/manifest.json", include_in_schema=False)
def serve_pwa_manifest():
  """Serve manifest.json."""
  pwa_manifest = os.path.join(os.path.dirname(__file__), "manifest.json")
  if os.path.exists(pwa_manifest):
    return FileResponse(pwa_manifest, media_type="application/json")
  return {"detail": "manifest.json missing"}


icons_dir = os.path.join(os.path.dirname(__file__), "icons")
if os.path.exists(icons_dir):
  app.mount("/icons", StaticFiles(directory=icons_dir), name="icons")

static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
  try:
    os.makedirs(static_dir)
  except OSError:
    pass
if os.path.exists(static_dir):
  app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
  import uvicorn

  logger.info(
      "[Starting] NDMA DisasterLens AI Backend v2.0 on http://localhost:8000"
  )
  uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)