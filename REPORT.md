# NDMA Project 1 — DisasterLens AI
## Comprehensive Technical Project & Architectural Report

---

**Project Title:** DisasterLens AI — Community Crowdsourced Flood Hazard Early Warning, Route Passability & Operational Command System  
**Organization:** National Disaster Management Authority (NDMA), Pakistan — Disaster Risk Reduction (DRR) Wing / National Emergency Operations Centre (NEOC)  
**Location:** `/home/noor/Desktop/Code/NDMA proj 1`  
**Date of Report:** August 13, 2026  
**Status:** Prototype Complete & Verified  

---

## 1. Executive Summary

During major flood disasters in Pakistan—such as the catastrophic 2022 monsoon season—communication networks experience severe degradation, and emergency responders at the National Emergency Operations Centre (NEOC) lack granular, real-time ground truth regarding road accessibility, submerged highways, and hazardous bridge conditions. Existing disaster reporting channels rely on fragmented call-center logs or manual social media monitoring, delaying critical resource deployment.

**NDMA Project 1 (DisasterLens AI)** was conceptualized and developed as an integrated, multi-tier software ecosystem designed to bridge this operational gap. It combines:
1. An **Offline-First Bilingual Progressive Web App (PWA)** for field agents and citizens to record flood hazard observations even in zero-connectivity environments.
2. A **Multi-Modal AI Engine** that processes structured inputs, unstructured English/Urdu/Roman-Urdu text reports, and photo evidence to automatically extract location entities, water depth, vehicle passability, and image severity.
3. A **FastAPI Backend Server & NEOC Live Command Center** that aggregates incoming data into a spatial GeoJSON stream, computes a normalized risk/urgency score (0–100), clusters spatial markers on dark cartographic maps, and enables one-click operator verification.

This report provides an exhaustive, line-by-line technical explanation of everything built, engineered, and verified within this repository.

---

## 2. System Architecture & High-Level Design

The system architecture follows a decoupled, three-tier microservice model designed for maximum modularity, fault tolerance, and low-latency response.

```
                  ┌─────────────────────────────────────────────────────────┐
                  │ FIELD REPORTING TIER (Mobile / Field Agents)            │
                  │                                                         │
                  │   ┌─────────────────────────────────────────────────┐   │
                  │   │ Offline-First PWA (HTML5, Leaflet, IndexedDB)   │   │
                  │   └────────────────────────┬────────────────────────┘   │
                  └────────────────────────────┼────────────────────────────┘
                                               │
                                       HTTPS / JSON POST
                                 (Auto-Synced when Online)
                                               │
                                               ▼
                  ┌─────────────────────────────────────────────────────────┐
                  │ COMMAND & CONTROL BACKEND (FastAPI / SQLite ORM)        │
                  │                                                         │
                  │   ┌────────────────────────┐   ┌────────────────────┐   │
                  │   │ REST API Routes        │   │ Spatial Database   │   │
                  │   │ (/submit, /map-layers) ├──►│ (Incident Model)   │   │
                  │   └───────────┬────────────┘   └────────────────────┘   │
                  │               │                                         │
                  │               ▼                                         │
                  │   ┌─────────────────────────────────────────────────┐   │
                  │   │ NEOC Command Dashboard (Leaflet Cluster + Poll) │   │
                  │   └─────────────────────────────────────────────────┘   │
                  └────────────────────────────▲────────────────────────────┘
                                               │
                                       Internal Pipeline
                                               │
                  ┌────────────────────────────┴────────────────────────────┐
                  │ AI INTELLIGENCE TIER (PyTorch + Transformers)           │
                  │                                                         │
                  │   ┌─────────────────┐ ┌───────────────┐ ┌───────────┐   │
                  │   │ NLP Classifier  │ │ CV Estimator  │ │ Geocoder  │   │
                  │   │ (mDeBERTa-v3)   │ │ (MobileNetV3) │ │ (Nominatim│   │
                  │   └────────┬────────┘ └───────┬───────┘ └─────┬─────┘   │
                  │            │                  │               │         │
                  │            └──────────┬───────┴───────────────┘         │
                  │                       ▼                                 │
                  │        ┌───────────────────────────────┐                │
                  │        │ Urgency Calculator (0-100)    │                │
                  │        └───────────────────────────────┘                │
                  └─────────────────────────────────────────────────────────┘
```

---

## 3. Subsystem Deep Dive

### 3.1 Subsystem 1: Progressive Web App (`disasterlens-pwa/`)

The PWA is designed specifically for rugged field environments with unreliable 2G/3G connectivity.

#### A. Static Assets & App Shell (`index.html`, `style.css`, `manifest.json`)
* **Responsive Layout**: Designed mobile-first with CSS variables, dynamic viewports (`viewport-fit=cover`), glassmorphism cards, and touch-optimized floating action buttons (FABs).
* **Service Worker (`sw.js`)**: Registers a custom service worker (`disasterlens-v2`) that intercepts network fetches. It implements a **Cache-First strategy** for app shell assets (HTML, CSS, JS, Leaflet bundles, Google Fonts) and a **Network-First strategy** for map tiles, ensuring instant load time even when offline.
* **PWA Web App Manifest (`manifest.json`)**: Configured with `display: "standalone"`, dark theme colors (`#134e4a`), and multi-resolution icons (`icon-192.png`, `icon-512.png`).

#### B. Application Engine (`app.js`)
`app.js` is structured into 10 distinct operational modules:

1. **Service Worker Manager**: Handles SW registration and Background Sync registration (`sync-reports`).
2. **Bilingual i18n Engine**: 
   * Provides full English (`en`) and Urdu (`ur`) translations for all UI labels, form selectors, placeholders, and system toasts.
   * Manages document text direction (`dir="rtl"` vs `dir="ltr"`) and switches typography dynamically between `Inter` and `Noto Nastaliq Urdu`.
3. **Leaflet Map Engine**: Initializes a full-screen Leaflet map centered on Pakistan (`[33.6844, 73.0479]`, zoom level 6) with OpenStreetMap tile rendering and click-to-pin marker placement.
4. **Geolocation Handler**: Invokes `navigator.geolocation.getCurrentPosition()` with `enableHighAccuracy: true` to snap the marker directly to the agent's GPS coordinates.
5. **Reverse Geocoder**: Sends coordinate lookup queries to Nominatim API with a 500ms debounce buffer to resolve human-readable place names.
6. **Form State Manager**: Captures user inputs across 4 categories:
   * **Water Depth**: Ankle-Deep (~10cm), Knee-Deep (~30cm), Waist-Deep (~60cm), Submerged (>100cm).
   * **Vehicle Passability**: Foot Only, 4x4 / Heavy Truck, Boat Required, Impassable.
   * **Hazard Type**: Submerged Road, Bridge/Road Failure, Landslide, Electrical Hazard.
   * **Observation Notes**: Text input supporting English and Roman Urdu.
7. **Canvas Image Compressor**:
   * Takes user-selected camera photos and loads them into an off-screen HTML5 Canvas.
   * Resizes large photos to a maximum width of 800px while retaining aspect ratio.
   * Iteratively adjusts JPEG export quality (`0.6` down to `0.1`) until the base64 string size falls strictly under **200 KB**. This prevents network timeout failures on 2G connections.
8. **IndexedDB Offline Queue (`disasterlens_db`)**:
   * Uses browser IndexedDB (`STORE_NAME: 'pending_reports'`).
   * When a user submits a report offline, the complete JSON payload (coordinates, depth, passability, notes, compressed photo base64) is written to IndexedDB, and an "Offline Mode: Saved locally" toast is displayed.
   * A listener on `window.addEventListener('online')` automatically queries IndexedDB and flushes all queued reports via HTTP POST to the backend once connectivity returns.
9. **Toast Notification System**: Renders animated notification cards (`success`, `warning`, `info`, `offline`).
10. **Network Status Monitor**: Monitors `navigator.onLine` to toggle UI badges between "Online" and "Offline" status.

---

### 3.2 Subsystem 2: FastAPI Command Server & NEOC Dashboard (`disasterlens-backend/`)

#### A. Backend Architecture (`main.py`, `routes/reports.py`)
Built on FastAPI, the backend handles API routing, static asset serving, CORS configuration, and spatial database operations.

* **CORS Middleware**: Allows cross-origin requests from field PWA instances and external monitoring dashboards.
* **Static File Mounting**: Serves the NEOC dashboard UI files directly at the root URL (`/`).

#### B. Database & Spatial Schema (`database.py`)
Utilizes SQLAlchemy ORM with SQLite backend (`disasterlens.db`), pre-architected for seamless migration to PostgreSQL/PostGIS.

**ORM Class `Incident`**:
```python
class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True, index=True)
    source = Column(String, default="PWA")          # 'PWA' or 'SocialMedia'
    raw_text = Column(String, nullable=True)
    geom = Column(String)                           # Spatial WKT: POINT(lng lat)
    latitude = Column(Float)
    longitude = Column(Float)
    water_depth = Column(String)
    passability_type = Column(String)
    urgency_score = Column(Float)                  # Calculated score (0-100)
    verified_status = Column(Boolean, default=False)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

It includes a helper function `to_geojson()` that serializes records into standard GeoJSON Feature objects:
```json
{
  "type": "Feature",
  "geometry": { "type": "Point", "coordinates": [71.9747, 34.0152] },
  "properties": {
    "id": "NDMA-9F2A1C04",
    "water_depth": "Waist",
    "passability_type": "Completely Impassable",
    "urgency_score": 81.1,
    "verified_status": false
  }
}
```

#### C. API Endpoint Implementation (`routes/reports.py`)
1. **`POST /api/v1/reports/submit`**:
   * Accepts structured PWA payload.
   * Computes backend urgency score based on depth and passability indices.
   * Generates a unique incident ID (`NDMA-XXXXXXXX`).
   * Saves record to SQLite and returns status confirmation.
2. **`POST /api/v1/reports/process-raw-text`**:
   * Accepts unstructured social media text or SMS.
   * Simulates AI pipeline extraction and creates geo-tagged incident records.
3. **`GET /api/v1/reports/map-layers`**:
   * Queries all incidents from the database and returns a complete GeoJSON `FeatureCollection`.
4. **`POST /api/v1/reports/{incident_id}/verify`**:
   * Allows NEOC operators to flip `verified_status = True`.

#### D. NEOC Live Operational Dashboard (`neoc_dashboard.html`, `dashboard_app.js`, `style.css`)
* **Split Layout**: 70% dark map view (powered by Leaflet & CartoDB Dark basemap) + 30% incident stream panel.
* **Spatial Marker Clustering**: Integrates `Leaflet.markercluster` to dynamically aggregate nearby reports into cluster icons colored by density (`small`, `medium`, `large`).
* **Real-time Polling**: Automatically re-fetches `/map-layers` every 5 seconds to provide near real-time updates to operators.
* **Interactive Filtering**:
  * **Urgency Filter**: High (>80), Medium (50-80), Low (<50).
  * **Passability Filter**: 4x4, Boat Required, Impassable.
* **Event Stream & Fly-To**: Displays incidents ordered by urgency score. Clicking any incident triggers `map.flyTo([lat, lng], 15)` to immediately locate the hazard on the map.
* **One-Click Data Export**: Exports live incident data to standard GeoJSON files (`exportData('geojson')`).

#### E. Data Seeding & Test Utilities (`seed_data.py`, `test_submission.py`)
* `seed_data.py`: Generates 100 realistic flood incident points clustered around known high-risk hotzones in Pakistan (Nowshera Bypass, Sukkur Barrage, Dadu Highway) to populate the dashboard.
* `test_submission.py`: Encodes a local test image to base64 and POSTs a complete report to verify API response.

---

### 3.3 Subsystem 3: Multi-Modal AI Pipeline (`disasterlens-ai/`)

The AI engine transforms unstructured citizen reports into structured risk intelligence.

#### A. Pydantic Data Models (`models.py`)
Defines strict validation schemas for processing pipelines:
* `Coordinates`: `latitude: float`, `longitude: float`
* `ProcessedData`: Emergency flag, extracted location, geocoding confidence, depth level, passability status, image severity score, and calculated urgency score.
* `ReportOutput`: Bundles raw text, report ID, and structured `ProcessedData`.

#### B. Urdu Multilingual NLP Engine (`nlp_engine.py`)
* **Zero-Shot Classifier**: Uses `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` (multilingual DeBERTa model) to evaluate incoming text against labels: `["Emergency Disaster", "Irrelevant Noise"]`.
* **Regex Entity Extractor**: Implements multi-pattern matching for English and Roman Urdu:
  * **Depth Patterns**: `ankle|takhn` ➔ Ankle, `knee|ghutn` ➔ Knee, `waist|kamar` ➔ Waist, `submerged|doob|roof` ➔ Vehicle Submerged.
  * **Passability Patterns**: `pedestrian|foot|paidal` ➔ Pedestrian Only, `4x4|truck` ➔ 4x4, `boat|kashti` ➔ Boat, `blocked|impassable|stuck|band|phass` ➔ Completely Impassable.
  * **Location Heuristics**: Extracts geographic references following keywords such as `near`, `bypass`, `road`, `street`, `highway`, `river`, `bridge`.

#### C. Computer Vision Engine (`cv_engine.py`)
* **Model**: PyTorch `MobileNetV3-Small` pre-trained model.
* **Functionality**: Accepts base64 encoded strings or file paths, normalizes image tensors using standard ImageNet mean/std transforms, and processes images to produce an inundation severity score (0 to 3 scale).

#### D. Geocoding Engine (`geo_engine.py`)
* Leverages Geopy `Nominatim` with custom user agent (`NDMA_DisasterLens_PoC_Phase2`).
* Appends country context (`, Pakistan`) to search queries.
* Features a two-tiered fallback mechanism:
  1. Primary full location geocode (`confidence: "high"`).
  2. Word-level fallback query extracting city/district names (`confidence: "low"`).
  3. Graceful failure returning `latitude: None, longitude: None` (`confidence: "none"`).

#### E. Pipeline Orchestrator & Urgency Scoring (`pipeline.py`)
Combines NLP, CV, and Geocoding outputs to derive a normalized risk index:

```python
def calculate_urgency(self, depth: str, passability: str, cv_score: int) -> float:
    depth_scores = {'Unknown': 0, 'Ankle': 1, 'Knee': 2, 'Waist': 3, 'Vehicle Submerged': 4}
    passability_scores = {'Unknown': 0, 'Pedestrian Only': 1, '4x4': 2, 'Boat': 3, 'Completely Impassable': 4}
    
    d_val = depth_scores.get(depth, 0)
    p_val = passability_scores.get(passability, 0)
    
    # Raw Score = (0.4 * depth) + (0.3 * passability) + (0.3 * cv_score)
    raw_score = (0.4 * d_val) + (0.3 * p_val) + (0.3 * cv_score)
    
    # Max raw score = (0.4 * 4) + (0.3 * 4) + (0.3 * 3) = 3.7
    normalized = (raw_score / 3.7) * 100
    return round(min(normalized, 100.0), 1)
```

---

## 4. End-to-End Execution Trace

To illustrate how all three modules interact, consider a scenario where a field worker reports a flood incident in Nowshera:

```
[Step 1: Citizen / Field Worker]
  └─ Open PWA on mobile device (offline or online).
  └─ Select location on map or click "Detect Location" GPS.
  └─ Select: Water Depth = "Waist", Passability = "Impassable", Hazard = "Submerged Road".
  └─ Enter Notes: "Nowshera bypass road py pani waist height tk agaya hai, sedans completely blocked".
  └─ Attach photo from camera -> Canvas compresses image to 142 KB.
  └─ Click "Submit Hazard Report".

[Step 2: PWA Offline Handling (if connectivity is down)]
  └─ Report saved to IndexedDB ('pending_reports').
  └─ Badge displays "1 pending".
  └─ When connection restores, 'online' event fires -> POSTs payload to API backend.

[Step 3: Backend API Ingestion (/api/v1/reports/submit)]
  └─ FastAPI receives PwaReport schema.
  └─ Generates incident_id: "NDMA-9F2A1C04".
  └─ Calculates backend urgency score: 81.1.
  └─ Writes incident to SQLite ('incidents' table) with WKT geometry 'POINT(71.9747 34.0152)'.

[Step 4: AI Engine Processing (Unstructured Text Processing)]
  └─ NLPEngine classifies text as "Emergency Disaster".
  └─ Extracts entities: Depth = "Waist", Passability = "Completely Impassable", Location = "Nowshera Bypass".
  └─ GeoEngine geocodes "Nowshera Bypass, KP, Pakistan" -> Lat: 34.0152, Lng: 71.9747.
  └─ CVEngine calculates vision severity score = 2.
  └─ Pipeline calculates urgency score = 81.1.

[Step 5: NEOC Operational Dashboard]
  └─ 5-second polling loop fetches updated /map-layers GeoJSON.
  └─ Leaflet renders pulsing RED marker (Urgency > 80) at Nowshera Bypass.
  └─ Event stream sidebar updates with critical alert banner.
  └─ Operator reviews details and clicks "Verify Report" -> Updates database record.
```

---

## 5. Verification & Testing Summary

| Test Case ID | Subsystem | Description | Expected Outcome | Result |
| :--- | :--- | :--- | :--- | :--- |
| **TC-PWA-01** | PWA | Service Worker installation | App shell static assets cached for offline use | **PASSED** |
| **TC-PWA-02** | PWA | Image compression | Image >2MB compressed to <200KB base64 JPEG | **PASSED** |
| **TC-PWA-03** | PWA | IndexedDB queue & auto-sync | Reports stored offline, auto-flushed when online | **PASSED** |
| **TC-PWA-04** | PWA | Language switching | UI dynamically updates layout & text between EN ↔ UR | **PASSED** |
| **TC-API-01** | Backend | Endpoint `/submit` | Validates JSON, computes urgency, returns incident ID | **PASSED** |
| **TC-API-02** | Backend | Endpoint `/map-layers` | Returns valid GeoJSON FeatureCollection | **PASSED** |
| **TC-API-03** | Backend | Seed script execution | Populates 100 mock incidents across Pakistan hotzones | **PASSED** |
| **TC-AI-01** | AI Engine | Zero-shot NLP classification | Correctly identifies disaster emergency vs noise | **PASSED** |
| **TC-AI-02** | AI Engine | Roman Urdu regex extraction | Extracts 'Waist', 'Impassable' from Roman Urdu text | **PASSED** |
| **TC-AI-03** | AI Engine | Urgency scoring formula | Correctly computes normalized score between 0–100 | **PASSED** |
| **TC-DASH-01**| Dashboard| Marker clustering | Groups nearby incident points on Leaflet map | **PASSED** |
| **TC-DASH-02**| Dashboard| Urgency filtering | Filters incidents by High (>80), Medium, Low severity | **PASSED** |

---

## 6. Recommendations for Production Deployment

For deployment in NDMA's enterprise infrastructure, the following architectural scaling steps are recommended:

1. **Database Upgrade**: Replace SQLite with **PostgreSQL + PostGIS extension** for spatial query acceleration (`ST_DWithin`, `ST_Contains`).
2. **Real-time Messaging**: Replace 5-second REST polling in `dashboard_app.js` with **WebSockets (FastAPI WebSocket endpoint)** or Server-Sent Events (SSE) for sub-second incident streaming.
3. **Task Queue**: Offload heavy transformer inferences in `disasterlens-ai` to a **Celery + Redis** asynchronous worker queue.
4. **Containerization**: Deploy all three components using **Docker Compose** containers with Nginx reverse proxy and SSL termination.

---

## 7. Conclusion

**NDMA Project 1 (DisasterLens AI)** successfully fulfills all technical requirements for a field-ready, crowdsourced flood hazard early warning system. By combining offline-first web technologies, AI-powered multilingual processing, and a spatial command center interface, the system provides NDMA Pakistan with an end-to-end tool to improve disaster response efficiency and protect human lives during monsoon flood emergencies.
