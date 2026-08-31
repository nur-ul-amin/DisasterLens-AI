# How to Run NDMA DisasterLens AI

This guide provides step-by-step instructions on how to start the backend server and access the different dashboards for the NDMA DisasterLens AI platform.

## Prerequisites

The project relies on a Python virtual environment to manage its dependencies. Make sure you are using a terminal (e.g., bash or zsh) on your Linux/macOS machine.

## 1. Start the Backend Server

The backend is built with FastAPI and runs on port `8000`. It includes the background worker that aggregates live disaster news every 10 seconds.

Open your terminal and run the following commands:

```bash
# 1. Navigate to the backend directory
cd "/home/noor/Desktop/Code/NDMA proj 1/disasterlens-backend"

# 2. Activate the virtual environment
source venv/bin/activate

# 3. (Optional) Install dependencies if you haven't already
# pip install -r requirements.txt

# 4. Run the FastAPI server using Python (or Uvicorn)
python main.py
```

*Note: You should see logs indicating that the background polling worker has started and the server is running on `http://0.0.0.0:8000`.*

## 2. Access the Dashboards

Once the server is running, you can access the various interfaces by opening these URLs in your web browser:

### 📡 Live Disaster News Dashboard (v2.0)
**URL:** [http://localhost:8000/news_panel.html](http://localhost:8000/news_panel.html)
* **What it is:** The primary multi-hazard live news dashboard. It features an interactive Leaflet map and a real-time auto-updating news feed on the right side. It displays aggregated data from GDACS, ReliefWeb, USGS, etc., clustered and scored by trust.

### 📱 PWA Field Reporting Interface (Phase 1)
**URL:** [http://localhost:8000/index.html](http://localhost:8000/index.html)
* **What it is:** The Progressive Web App (PWA) designed for field agents to report incidents directly from the ground. It supports offline caching and allows uploading photos and structured data (water depth, passability).

### 🌍 Legacy NEOC Dashboard (Phase 3)
**URL:** [http://localhost:8000/neoc_dashboard.html](http://localhost:8000/neoc_dashboard.html)
* **What it is:** The older version of the National Emergency Operations Center dashboard. It displays field reports stored in the database.

### 📖 API Documentation
**URL:** [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
* **What it is:** Interactive Swagger documentation for the backend API (endpoints for map layers, feed, worker status, and report submission).

## 3. Stopping the Server

To stop the server, simply go to the terminal where it's running and press `Ctrl + C`. The FastAPI lifespan events will ensure the background news aggregation worker stops cleanly.
