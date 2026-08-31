# Comprehensive Project Report: NDMA DisasterLens AI v2.0

## Executive Summary
This document provides a comprehensive overview of the development, architecture, and deployment of the **NDMA DisasterLens AI** platform over the past four weeks. The system was built for the Pakistan National Disaster Management Authority (NDMA) to provide a centralized, AI-powered Command & Control platform. The primary goal was to create a robust system that can ingest field reports (via a Progressive Web App), process unstructured social media data using AI, and aggregate live disaster news from verified global sources (GDACS, ReliefWeb, USGS, etc.), all visualized on a real-time geo-spatial dashboard.

---

## 4-Week Development Timeline

### Week 1: Foundation & Offline-First Field Reporting (Phase 1)
* **Goal:** Build a robust, offline-capable reporting tool for field agents in disaster zones with poor connectivity.
* **Achievements:**
  * Developed a **Progressive Web App (PWA)** using vanilla JavaScript, HTML, and CSS.
  * Implemented a Service Worker (`sw.js`) for offline-first caching of app shell assets.
  * Created structured reporting forms allowing agents to submit location (GPS), water depth, vehicle passability, and photos.
  * Established the foundational FastAPI backend (`main.py`, `database.py`) using SQLite to store structured incident data.

### Week 2: AI Pipeline & Unstructured Data Processing (Phase 2)
* **Goal:** Enable the ingestion and automated processing of unstructured disaster reports (e.g., from social media) using artificial intelligence.
* **Achievements:**
  * Built the **AI Engine** (`pipeline.py`) consisting of three main modules:
    * **NLP Engine (`nlp_engine.py`):** Utilized a Zero-Shot Classification model (mDeBERTa-v3-base via HuggingFace `transformers`) to identify emergencies and extract entities (depth, passability, location) from English and Roman Urdu text.
    * **Geo Engine (`geo_engine.py`):** Integrated Nominatim (`geopy`) to convert extracted text locations into standard WGS84 coordinates.
    * **CV Engine (`cv_engine.py`):** Implemented a pre-trained MobileNetV3 (via `torchvision`) to estimate severity from uploaded images.
  * Developed an urgency scoring algorithm combining water depth, passability, and visual severity to generate a standardized 0-100 risk score.

### Week 3: NEOC Dashboard & Geo-Spatial Visualization (Phase 3)
* **Goal:** Create a centralized dashboard for the National Emergency Operations Center (NEOC) to visualize all verified and unverified incidents.
* **Achievements:**
  * Developed the legacy **NEOC Dashboard** (`neoc_dashboard.html`).
  * Integrated **Leaflet.js** for interactive map rendering, bounded strictly to Pakistan's geographical hotzones.
  * Created backend API endpoints (`routes/reports.py`) to expose database incidents as GeoJSON FeatureCollections.
  * Seeded the database (`seed_data.py`) with realistic, Pakistan-specific flood reports and verified sources to simulate a live environment.

### Week 4: Live Disaster News Aggregation Subsystem (Phase 4 / v2.0)
* **Goal:** Integrate real-time, global disaster news feeds, verify them, and display them seamlessly on the dashboard.
* **Achievements:**
  * Developed a highly concurrent **News Aggregator Subsystem** fetching data from GDACS, USGS, ReliefWeb, GDELT, and NDMA RSS feeds (`fetcher.py`).
  * Created a sophisticated data processing pipeline:
    * **Normalizer (`normalizer.py`):** Standardizes payloads into a single schema and filters out news older than 24 hours.
    * **Geocoder (`geocoder.py`):** Resolves missing coordinates with Nominatim and country-centroid fallbacks.
    * **Classifier (`classifier.py`):** Categorizes hazards (Flood, Earthquake, Cyclone, etc.) using keyword patterns.
    * **Clusterer (`clusterer.py`):** Deduplicates and groups events spatially (within 50km), temporally (within 6 hrs), and semantically.
    * **Scorer (`scorer.py`):** Assigns a Trust & Reliability score (0-100%) based on source authority, multi-source corroboration, media completeness, and temporal freshness.
  * Built the **Live Disaster News Dashboard** (`news_panel.html` and `news_layer.js`) with an auto-polling engine (every 10 seconds), dynamic Leaflet map layers, flashing animations for new items, and a scrollable news feed.
  * Implemented a thread-safe, in-memory TTL **Cache** (`cache.py`) to serve GeoJSON and feed data with sub-millisecond latency.

---

## Technology Stack & Languages Used

### Languages
* **Python 3:** Core backend language, data processing, and AI execution.
* **JavaScript (ES6):** Frontend interactivity, mapping logic, PWA Service Worker, and asynchronous API polling.
* **HTML5 & CSS3:** UI structure, responsive design, custom animations, and layout styling (Vanilla CSS, no bulky frameworks).

### Backend Frameworks & Libraries
* **FastAPI:** High-performance web framework for the API layer.
* **SQLAlchemy & GeoAlchemy2:** ORM for database management.
* **HTTPX & Feedparser:** Asynchronous HTTP client and RSS parser for news fetching.
* **Pydantic:** Data validation and settings management.
* **SQLite:** Lightweight relational database (with `mod_spatialite` for spatial queries).

### AI & Machine Learning
* **PyTorch & Torchvision:** Core deep learning framework for the Computer Vision engine (MobileNetV3).
* **HuggingFace Transformers:** NLP execution utilizing zero-shot classification (mDeBERTa-v3-base).
* **Geopy (Nominatim):** Geocoding and reverse-geocoding for the Geo Engine.

### Frontend
* **Leaflet.js:** Industry-standard open-source JavaScript library for mobile-friendly interactive maps.
* **Progressive Web App (PWA):** Enabling offline-first capabilities using `manifest.json` and Service Workers.

---

## Core System Functionality & Data Pipeline

The crowning achievement of this platform is the **Real-Time News Aggregation Pipeline**. Here is how data flows from external sources to the user's screen:

1. **Ingestion (`fetcher.py`):** A background worker runs every 10 seconds, using `asyncio` to concurrently fetch data from various global and local disaster APIs and RSS feeds.
2. **Normalization (`normalizer.py`):** Incoming heterogeneous data (GeoRSS, JSON, Atom) is standardized into a uniform `NormalizedNewsItem`. Any data older than 24 hours is instantly discarded.
3. **Enrichment (`geocoder.py` & `classifier.py`):** 
   * The system attempts to resolve exact coordinates for the event.
   * Text is analyzed to classify the exact hazard type (e.g., Flood, Landslide) and assigned corresponding UI tokens (emojis and colors).
4. **Clustering (`clusterer.py`):** To prevent dashboard clutter, multiple reports about the same incident are merged into a single `DisasterCluster`. Events are merged if they are within 50km geographically, 6 hours temporally, or share significant semantic overlap.
5. **Trust Verification (`scorer.py`):** A deterministic algorithm calculates a trust score. High authority sources (like GDACS) contribute heavily, while multi-source verification and media completeness add bonus points. Clusters are labeled as "High Trust" (Verified), "Moderate" (Cross-Check), or "Unverified".
6. **Caching (`cache.py`):** The final clusters are transformed into a GeoJSON FeatureCollection and a flat list, then stored in a rapid in-memory cache to prevent database/API bottlenecks.
7. **Frontend Rendering (`news_layer.js` & `news_panel.html`):** The browser polls the API every 10 seconds. It seamlessly updates the Leaflet map markers and the right-side news panel, applying color-coded trust badges and flashing animations to newly discovered incidents.

---

## Future Improvements & Scalability

While the current system is highly functional and serves as an excellent operational prototype, the following steps are recommended for enterprise-level deployment:

1. **Database Migration:** Migrate from SQLite to **PostgreSQL with PostGIS**. This will dramatically improve spatial query performance and support massive concurrency.
2. **Dedicated Caching Layer:** Replace the in-memory Python dictionary cache with **Redis** to allow scaling the FastAPI backend across multiple worker processes or servers.
3. **AI Model Fine-Tuning:** 
   * **NLP:** Fine-tune the DeBERTa model specifically on disaster-related Roman Urdu and local dialects to improve entity extraction accuracy.
   * **CV:** Replace the generic MobileNet model with a custom model fine-tuned specifically on flood and earthquake imagery to accurately assess damage severity rather than generic image classification.
4. **WebSockets for Real-Time Updates:** Transition the frontend from a 10-second polling interval (HTTP GET) to a WebSocket connection to push updates instantly to connected clients with lower overhead.
5. **Authentication & Roles:** Implement JWT-based authentication to restrict access to the NEOC dashboard and allow authorized verification of incidents by officers.
6. **Broader Integration:** Integrate direct API hooks for platforms like WhatsApp Business API to allow citizens to report incidents via chat bots directly into the pipeline.
