# NDMA Project 1 — DisasterLens AI
> **Community Crowdsourced Flood Hazard Early Warning, Route Passability & Operational Command System**  
> *Developed for National Disaster Management Authority (NDMA), Pakistan — Disaster Risk Reduction (DRR) Wing & National Emergency Operations Centre (NEOC)*

---

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Leaflet.js](https://img.shields.io/badge/Leaflet-1.9.4-green.svg)](https://leafletjs.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-EE4C2C.svg)](https://pytorch.org/)
[![PWA Ready](https://img.shields.io/badge/PWA-Offline--First-134e4a.svg)](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps)

---

## 📌 Executive Overview

**NDMA Project 1 (DisasterLens AI)** is an end-to-end, multi-tier disaster management platform designed to address critical communication and route passability challenges during catastrophic monsoon flooding in Pakistan. 

During severe flood events (e.g., 2022 monsoon floods), physical infrastructure is breached, telecommunications suffer degraded 2G/3G connectivity, and centralized emergency centers lack real-time ground truth regarding road inundation, bridge failures, and vehicle accessibility. 

**DisasterLens AI** solves this by establishing a three-tiered ecosystem:
1. **Offline-First Bilingual Progressive Web App (PWA)**: Empowers field agents and citizens to log crowdsourced flood reports, water depths, vehicle passability, and compressed photo evidence with full offline queuing capabilities.
2. **AI & Geospatial Risk Engine**: Leverages zero-shot NLP transformers (mDeBERTa-v3), computer vision (MobileNetV3), and reverse geocoding to parse unstructured English/Urdu/Roman-Urdu reports into structured spatial data and calculate normalized risk/urgency scores.
3. **NEOC Live Command Dashboard & REST API**: Provides operational commanders at NEOC with real-time geospatial clustering, live event streaming, passability filtering, automated urgency scoring, and one-click incident verification.

---

## 🏗️ System Architecture & Subsystem Layout

The repository is structured into three decoupled sub-systems:

```
NDMA proj 1/
├── disasterlens-pwa/         # Module 1: Mobile-First Offline PWA (Field Reporting)
│   ├── index.html             # App UI layout & bilingual drawer modal
│   ├── style.css              # Custom responsive styles & glassmorphism theme
│   ├── app.js                 # Core PWA engine (Leaflet, GPS, IDB queue, Canvas compression)
│   ├── sw.js                  # Service Worker for offline app-shell caching
│   ├── manifest.json          # PWA metadata & standalone display configuration
│   └── icons/                 # PWA application icons (192x192, 512x512)
│
├── disasterlens-backend/     # Module 2: FastAPI Command Server & NEOC Dashboard
│   ├── main.py                # FastAPI entry point, CORS middleware & static file routes
│   ├── database.py            # SQLAlchemy spatial database engine & Incident ORM schema
│   ├── neoc_dashboard.html    # NEOC Command Center split-screen operational UI
│   ├── dashboard_app.js       # Live Leaflet Map rendering, marker clustering & polling engine
│   ├── style.css              # Command Center dark mode theme & alert stream styling
│   ├── seed_data.py           # Mock flood incident generator (Pakistan hotzones)
│   ├── test_submission.py     # End-to-end API test script with base64 photo encoding
│   ├── disasterlens.db       # SQLite database instance (auto-generated)
│   └── routes/
│       └── reports.py         # REST API routes (/submit, /process-raw-text, /map-layers, /verify)
│
└── disasterlens-ai/          # Module 3: Multi-Modal AI & Geocoding Pipeline
    ├── models.py              # Pydantic data schemas (ProcessedData, ReportOutput, Coordinates)
    ├── nlp_engine.py          # Multilingual zero-shot classifier (mDeBERTa) & Urdu regex entity parser
    ├── cv_engine.py           # PyTorch MobileNetV3 image severity estimator
    ├── geo_engine.py          # Geopy Nominatim reverse geocoding engine with Pakistan context
    ├── pipeline.py            # Central AI pipeline & normalized Urgency Scoring formula
    └── requirements.txt       # Dependencies (transformers, torch, geopy, pydantic, Pillow)
```

---

## ⚡ Core Technical Features

### 📱 1. Offline-First Bilingual PWA (`disasterlens-pwa`)
* **Service Worker Cache Strategy**: Implements Cache-First caching (`sw.js`) for app shell static assets (HTML, CSS, JS, Leaflet JS/CSS, OSM tiles) allowing full functionality in 0-connectivity environments.
* **Client-Side Image Compression**: Utilizes an off-screen HTML5 Canvas API in `app.js` to resize camera captures to max 800px width and iteratively compress JPEGs to `<200KB` before storage, reducing bandwidth usage by up to 95%.
* **IndexedDB Offline Queue (`disasterlens_db`)**: Reports created while offline are queued in browser storage. The `window.addEventListener('online')` trigger flushes and syncs queued reports to the backend automatically.
* **Bilingual i18n Engine**: Supports instant seamless English and Urdu (`en` ↔ `ur`) switching with dynamic DOM text replacement and Right-to-Left (RTL) layout adjustment.
* **GPS & Leaflet Pinning**: HTML5 Geolocation API with high-accuracy GPS tracking, draggable pin location marker, and Nominatim reverse geocoding.

### 🧠 2. AI Intelligence Engine (`disasterlens-ai`)
* **Zero-Shot NLP Classification**: Employs `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` transformer model (CPU-optimized) to classify unstructured text into emergency vs non-emergency categories across English, Urdu, and Roman Urdu.
* **Urdu Entity Extraction**: Regex-based heuristic parser for water depth levels (*Ankle, Knee, Waist, Submerged*) and passability (*Pedestrian, 4x4, Boat, Impassable*) matching English and Roman Urdu keywords (`takhn`, `ghutn`, `kamar`, `doob`, `kashti`, `phass`).
* **Computer Vision Flood Estimator**: Uses PyTorch MobileNetV3-Small to decode base64/file images and estimate inundation severity scores (0 to 3 scale).
* **Automated Risk Scoring Formula**:
  $$\text{Urgency Score} = \left( \frac{0.4 \times D + 0.3 \times P + 0.3 \times V}{3.7} \right) \times 100$$
  *Where $D$ = Water Depth (0-4), $P$ = Passability (0-4), and $V$ = Computer Vision Severity (0-3).*

### 🖥️ 3. NEOC Command & Control Dashboard (`disasterlens-backend`)
* **FastAPI Microservice Backend**: Fully async endpoints for structured PWA ingestion, raw text AI ingestion, GeoJSON map layer generation, and operational verification.
* **Spatial GeoJSON Layer Generator**: Serves live incident features (`/api/v1/reports/map-layers`) for spatial mapping engines.
* **Leaflet Marker Clustering**: Visual heatmap aggregation using `Leaflet.markercluster` to group dense disaster points and prevent visual clutter during high-volume reporting.
* **Live Command Center UI**: 70/30 spatial map/sidebar split layout with real-time polling (5s interval), color-coded severity markers (Red >80, Yellow 50-80, Green <50), click-to-fly map positioning, and GeoJSON data export.

---

## 📊 Database Schema & API Reference

### Data Model: `Incident` Table (`disasterlens-backend/database.py`)

| Column Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `String` | Primary Key, Indexed | Unique incident ID (e.g. `NDMA-8A1B2C3D`) |
| `source` | `String` | Default: `'PWA'` | Source channel (`'PWA'` or `'SocialMedia'`) |
| `raw_text` | `String` | Nullable | Observation notes / incoming text |
| `geom` | `String` | Nullable | Spatial Point WKT (`POINT(lng lat)`) |
| `latitude` | `Float` | Required | WGS84 Latitude coordinate |
| `longitude` | `Float` | Required | WGS84 Longitude coordinate |
| `water_depth` | `String` | Required | `Ankle`, `Knee`, `Waist`, `Vehicle Submerged` |
| `passability_type`| `String` | Required | `Pedestrian Only`, `4x4`, `Boat`, `Completely Impassable` |
| `urgency_score` | `Float` | Required | Calculated risk index (0.0 to 100.0) |
| `verified_status` | `Boolean` | Default: `False` | Operator verification state |
| `image_url` | `String` | Nullable | Base64 string or stored photo URL |
| `created_at` | `DateTime` | Auto timestamp | Record creation timestamp |

---

### Key API Endpoints (`/api/v1/reports`)

#### 1. `POST /api/v1/reports/submit`
Ingests structured reports submitted from the PWA.
* **Request Payload**:
  ```json
  {
    "timestamp": "2026-08-13T14:00:00Z",
    "location": { "lat": 34.0152, "lng": 71.9747, "address": "Nowshera Bypass, KP" },
    "assessment": {
      "waterDepth": "Waist",
      "vehiclePassability": "Completely Impassable",
      "hazardType": "submerged_road"
    },
    "notes": "Water rising fast near bypass bridge, sedan cars stranded.",
    "photo": "data:image/jpeg;base64,...",
    "photoSizeKB": 142
  }
  ```
* **Response**:
  ```json
  {
    "status": "success",
    "incident_id": "NDMA-9F2A1C04",
    "urgency": 81.1
  }
  ```

#### 2. `POST /api/v1/reports/process-raw-text`
Ingests unstructured text (e.g. social media feeds or SMS broadcasts).
* **Request Payload**:
  ```json
  {
    "text": "Nowshera bypass road py pani waist height tk agaya hai, sedans completely blocked",
    "source": "SocialMedia"
  }
  ```

#### 3. `GET /api/v1/reports/map-layers`
Returns a standard GeoJSON FeatureCollection for mapping engines.

#### 4. `POST /api/v1/reports/{incident_id}/verify`
Toggles operator verification status for a specific incident.

---

## 🚀 Setup & Execution Guide

### Prerequisites
* Python 3.10 or higher
* `pip` package manager
* Web browser (Chrome, Edge, Firefox, Safari)

---

### Step 1: Environment Setup & Backend Launch

1. Navigate to the backend directory:
   ```bash
   cd "NDMA proj 1/disasterlens-backend"
   ```

2. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # On Linux/macOS
   # .venv\Scripts\activate     # On Windows
   ```

3. Install requirements:
   ```bash
   pip install fastapi uvicorn sqlalchemy geoalchemy2 shapely requests
   ```

4. Seed mock disaster data (Optional):
   ```bash
   python seed_data.py
   ```

5. Launch the FastAPI server:
   ```bash
   python main.py
   ```
   *The backend server will run at:* **`http://localhost:8000`**  
   *The NEOC Command Center UI will be live at:* **`http://localhost:8000/`**  
   *Interactive API Docs (Swagger):* **`http://localhost:8000/docs`**

---

### Step 2: Launching the AI Pipeline

1. In a new terminal, navigate to the AI directory:
   ```bash
   cd "NDMA proj 1/disasterlens-ai"
   ```

2. Install AI pipeline dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Execute pipeline test script:
   ```bash
   python pipeline.py
   ```

---

### Step 3: Running & Testing the PWA

1. Navigate to the PWA directory:
   ```bash
   cd "NDMA proj 1/disasterlens-pwa"
   ```

2. Serve using any static HTTP server (e.g. Python's built-in HTTP server or Live Server):
   ```bash
   python -m http.server 3000
   ```

3. Open **`http://localhost:3000`** in your browser.
4. Test offline capabilities by setting Developer Tools Network tab to **"Offline"**, creating a report, and restoring connectivity to test automatic queue synchronization.

---

## 🧪 System Verification & Test Executions

### Running Automated Test Submission
To test the backend report ingestion flow with base64 image encoding, run:
```bash
python disasterlens-backend/test_submission.py
```

### Verification Checklist
- [x] Service worker installs and pre-caches app shell (`disasterlens-v2`).
- [x] Form selections correctly compute urgency score on backend ($0-100$).
- [x] Canvas compresses images above 200KB down to $<200\text{KB}$.
- [x] IndexedDB stores offline reports and flushes upon network reconnection.
- [x] NEOC Dashboard updates every 5 seconds with clustered Leaflet markers.
- [x] Urdu translation toggle correctly dynamically formats RTL text.

---

## 📄 License & Attribution

Developed as a demonstration prototype for **NDMA Pakistan (DRR Wing)**.  
*Architected and engineered for disaster resilience and emergency route passability evaluation.*
