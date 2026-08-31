/**
 * ============================================================================
 * news_layer.js — Live Disaster News Polling Engine & Leaflet Integration
 * ============================================================================
 * NDMA DisasterLens AI — News Aggregation Subsystem Frontend
 *
 * ARCHITECTURE:
 *   - NewsLayerManager class controls all polling, rendering, and state
 *   - setInterval(10,000ms) polls /api/v1/news/map-layers for fresh GeoJSON
 *   - Custom Leaflet layer with color-coded trust markers & category icons
 *   - DOM-based news panel renders without framework overhead
 *   - Subtle CSS animation highlights newly arrived items
 *
 * INTEGRATION:
 *   - Include this file in news_panel.html
 *   - Call: const nlm = new NewsLayerManager(map, panelContainerId);
 *   - Call: nlm.startPolling();
 * ============================================================================
 */

'use strict';

// ─── Configuration ────────────────────────────────────────────────────────────
const NEWS_CONFIG = {
    API_BASE: 'http://localhost:8000',
    MAP_LAYERS_URL: 'http://localhost:8000/api/v1/news/map-layers',
    FEED_URL: 'http://localhost:8000/api/v1/news/feed',
    STATUS_URL: 'http://localhost:8000/api/v1/news/status',
    POLL_INTERVAL_MS: 10000,
    MAP_CENTER: [30.3753, 69.3451],  // Pakistan centroid
    MAP_ZOOM: 5,
    MAX_ZOOM: 18,
};

// ─── Hazard visual definitions ────────────────────────────────────────────────
const HAZARD_ICONS = {
    'Flood':        { emoji: '🌊', color: '#3b82f6' },
    'GLOF':         { emoji: '🧊', color: '#06b6d4' },
    'Landslide':    { emoji: '🏔️', color: '#92400e' },
    'Earthquake':   { emoji: '🌍', color: '#dc2626' },
    'Avalanche':    { emoji: '❄️', color: '#e0f2fe' },
    'Severe Storm': { emoji: '⛈️', color: '#7c3aed' },
    'Drought':      { emoji: '☀️', color: '#d97706' },
    'Heatwave':     { emoji: '🔥', color: '#ea580c' },
    'Cyclone':      { emoji: '🌀', color: '#9333ea' },
    'Wildfire':     { emoji: '🔥', color: '#ef4444' },
    'Unknown':      { emoji: '⚠️', color: '#6b7280' },
};

// ─── Trust color definitions ──────────────────────────────────────────────────
const TRUST_COLORS = {
    'High Trust':  { bg: '#14532d', border: '#22c55e', text: '#22c55e', badge: '✅ VERIFIED' },
    'Moderate':    { bg: '#78350f', border: '#f59e0b', text: '#f59e0b', badge: '⚠️ CROSS-CHECK' },
    'Unverified':  { bg: '#7f1d1d', border: '#ef4444', text: '#ef4444', badge: '❌ UNVERIFIED' },
};

// ─── Utility functions ────────────────────────────────────────────────────────

function timeAgo(isoString) {
    if (!isoString) return '—';
    const now = Date.now();
    const past = new Date(isoString).getTime();
    const diff = Math.floor((now - past) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
}

function formatScore(score) {
    return Math.round(score || 0);
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ─── Custom Leaflet Marker Icon Factory ──────────────────────────────────────

function createHazardIcon(category, trustLabel) {
    const hazard = HAZARD_ICONS[category] || HAZARD_ICONS['Unknown'];
    const trust = TRUST_COLORS[trustLabel] || TRUST_COLORS['Unverified'];

    const size = trustLabel === 'High Trust' ? 44 : trustLabel === 'Moderate' ? 40 : 36;

    const svgIcon = `
      <div style="
        width: ${size}px; height: ${size}px;
        background: ${trust.bg};
        border: 2.5px solid ${trust.border};
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: ${size * 0.44}px;
        box-shadow: 0 0 ${trustLabel === 'High Trust' ? '10px' : '4px'} ${trust.border}88,
                    0 2px 8px rgba(0,0,0,0.6);
        cursor: pointer;
        transition: transform 0.2s;
        position: relative;
      ">
        ${hazard.emoji}
        ${trustLabel === 'High Trust' ? `<div style="
          position: absolute; top: -3px; right: -3px;
          width: 12px; height: 12px;
          background: #22c55e; border-radius: 50%;
          border: 1.5px solid #0a0f1e;
          animation: pulse-verified 2s infinite;
        "></div>` : ''}
      </div>`;

    return L.divIcon({
        html: svgIcon,
        className: '',
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
        popupAnchor: [0, -size / 2 - 4],
    });
}

// ─── Popup HTML Factory ───────────────────────────────────────────────────────

function buildPopupHtml(props) {
    const trust = TRUST_COLORS[props.trust_label] || TRUST_COLORS['Unverified'];
    const hazard = HAZARD_ICONS[props.category] || HAZARD_ICONS['Unknown'];
    const sourceList = (props.source_refs || []).slice(0, 4)
        .map(ref => `<a href="${escapeHtml(ref.url)}" target="_blank" rel="noopener"
            style="color:#60a5fa; font-size:11px; display:block; margin-bottom:2px;
            white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:260px;">
            🔗 ${escapeHtml(ref.name)}</a>`).join('');

    const clusterBadge = props.cluster_size > 1
        ? `<span style="background:#1e293b; border:1px solid #334155; color:#94a3b8;
            padding:2px 8px; border-radius:12px; font-size:10px; margin-left:8px;">
            ${props.cluster_size} sources</span>` : '';

    return `
    <div style="
        font-family: 'Inter', 'Segoe UI', sans-serif;
        background: #0f172a; color: #e2e8f0;
        border-radius: 12px; overflow: hidden;
        width: 290px; font-size: 13px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    ">
      ${props.image_url ? `<div style="
            width: 100%; height: 120px; overflow: hidden;
            background: #1e293b;">
            <img src="${escapeHtml(props.image_url)}"
                 style="width:100%; height:100%; object-fit:cover; opacity:0.9;"
                 onerror="this.parentElement.style.display='none'" />
          </div>` : ''}

      <div style="padding: 14px;">
        <!-- Header -->
        <div style="display:flex; align-items:center; gap:6px; margin-bottom:8px;">
          <span style="font-size:18px;">${hazard.emoji}</span>
          <span style="
              background: ${hazard.color}22;
              color: ${hazard.color};
              border: 1px solid ${hazard.color}55;
              padding: 2px 8px; border-radius: 20px; font-size: 11px; font-weight:600;">
            ${escapeHtml(props.category)}</span>
          ${clusterBadge}
        </div>

        <!-- Title -->
        <div style="font-weight:600; font-size:13px; line-height:1.4;
                    color:#f1f5f9; margin-bottom:8px;">
          ${escapeHtml(props.title)}
        </div>

        <!-- Trust Score -->
        <div style="
            display:flex; align-items:center; justify-content:space-between;
            background: ${trust.bg}; border: 1px solid ${trust.border};
            border-radius: 8px; padding: 6px 10px; margin-bottom:10px;">
          <span style="color:${trust.text}; font-size:11px; font-weight:700;">
            ${trust.badge}</span>
          <span style="
              font-size:20px; font-weight:800; color:${trust.text};">
            ${formatScore(props.trust_score)}<span style="font-size:12px;">%</span></span>
        </div>

        <!-- Location & Time -->
        <div style="color:#64748b; font-size:11px; margin-bottom:10px;">
          📍 ${escapeHtml(props.location_name)} &nbsp;·&nbsp;
          🕐 ${timeAgo(props.published_at)}
        </div>

        <!-- Source Links -->
        <div style="border-top:1px solid #1e293b; padding-top:8px;">
          <div style="color:#475569; font-size:10px; font-weight:600;
                      text-transform:uppercase; margin-bottom:4px;">Sources</div>
          ${sourceList || '<span style="color:#475569; font-size:11px;">No source link</span>'}
        </div>
      </div>
    </div>`;
}

// ─── Main NewsLayerManager Class ──────────────────────────────────────────────

class NewsLayerManager {
    constructor(map, panelContainerId, statusBarId = null) {
        this.map = map;
        this.panelEl = document.getElementById(panelContainerId);
        this.statusBarEl = statusBarId ? document.getElementById(statusBarId) : null;
        this.pollInterval = null;
        this.geoJsonLayer = null;
        this.lastFeatureIds = new Set();
        this.totalPolls = 0;
        this.isPolling = false;
        this.currentFilter = { category: null, minTrust: null };
    }

    // ── Polling Control ──────────────────────────────────────────────────────

    startPolling() {
        if (this.isPolling) return;
        this.isPolling = true;
        console.log('[NewsLayer] Starting poll loop (every', NEWS_CONFIG.POLL_INTERVAL_MS, 'ms)');

        // Immediate first fetch
        this._fetchAndRender();

        // Recurring interval
        this.pollInterval = setInterval(() => {
            this._fetchAndRender();
        }, NEWS_CONFIG.POLL_INTERVAL_MS);
    }

    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
        this.isPolling = false;
        console.log('[NewsLayer] Polling stopped');
    }

    pausePolling() { this.stopPolling(); }
    resumePolling() { this.startPolling(); }

    // ── Core Fetch + Render ──────────────────────────────────────────────────

    async _fetchAndRender() {
        try {
            const resp = await fetch(NEWS_CONFIG.MAP_LAYERS_URL, {
                cache: 'no-cache',
                headers: { 'Accept': 'application/json' }
            });

            if (!resp.ok) {
                console.warn('[NewsLayer] HTTP', resp.status);
                return;
            }

            const geojson = await resp.json();
            this.totalPolls++;

            this._renderMapLayer(geojson);
            this._renderNewsPanel(geojson.features || []);
            this._updateStatusBar(geojson.metadata);

            console.log('[NewsLayer] Poll #' + this.totalPolls +
                ' | ' + (geojson.features || []).length + ' clusters');

        } catch (err) {
            console.error('[NewsLayer] Fetch error:', err);
            this._setStatusOffline();
        }
    }

    // ── Leaflet Map Layer ────────────────────────────────────────────────────

    _renderMapLayer(geojson) {
        const features = geojson.features || [];
        const currentIds = new Set(features.map(f => f.properties?.cluster_id));

        // Detect new items for flash animation
        const newIds = [...currentIds].filter(id => !this.lastFeatureIds.has(id));
        this.lastFeatureIds = currentIds;

        // Remove old layer
        if (this.geoJsonLayer) {
            this.map.removeLayer(this.geoJsonLayer);
        }

        // Apply current filters
        const filtered = features.filter(f => {
            const p = f.properties;
            if (this.currentFilter.category &&
                p.category?.toLowerCase() !== this.currentFilter.category.toLowerCase()) return false;
            if (this.currentFilter.minTrust && p.trust_score < this.currentFilter.minTrust) return false;
            return true;
        });

        this.geoJsonLayer = L.geoJSON({ type: 'FeatureCollection', features: filtered }, {
            pointToLayer: (feature, latlng) => {
                const p = feature.properties;
                const marker = L.marker(latlng, {
                    icon: createHazardIcon(p.category, p.trust_label),
                    title: p.title,
                    zIndexOffset: Math.round(p.trust_score) * 10,
                });

                // Popup
                marker.bindPopup(buildPopupHtml(p), {
                    maxWidth: 300,
                    className: 'news-popup',
                });

                // Flash new markers
                if (newIds.includes(p.cluster_id)) {
                    setTimeout(() => {
                        const el = marker.getElement();
                        if (el) {
                            el.style.animation = 'marker-flash 1s ease 3';
                        }
                    }, 100);
                }

                return marker;
            },
        }).addTo(this.map);
    }

    // ── News Panel ───────────────────────────────────────────────────────────

    _renderNewsPanel(features) {
        if (!this.panelEl) return;

        if (!features.length) {
            this.panelEl.innerHTML = `
                <div class="no-news-placeholder">
                    <div style="font-size:48px; margin-bottom:16px;">📡</div>
                    <div>Fetching live disaster updates...</div>
                    <div style="color:#475569; font-size:12px; margin-top:8px;">
                        Polling every 10 seconds</div>
                </div>`;
            return;
        }

        // Sort by trust score desc
        const sorted = [...features].sort((a, b) =>
            (b.properties.trust_score || 0) - (a.properties.trust_score || 0));

        const html = sorted.map((f, idx) => this._buildCardHtml(f.properties, idx)).join('');
        this.panelEl.innerHTML = html;

        // Attach "locate on map" button handlers
        this.panelEl.querySelectorAll('[data-lat][data-lng]').forEach(btn => {
            btn.addEventListener('click', () => {
                const lat = parseFloat(btn.dataset.lat);
                const lng = parseFloat(btn.dataset.lng);
                const clusterId = btn.dataset.cluster;
                this.map.flyTo([lat, lng], 9, { duration: 1.2 });

                // Open corresponding popup
                if (this.geoJsonLayer) {
                    this.geoJsonLayer.eachLayer(layer => {
                        if (layer.feature?.properties?.cluster_id === clusterId) {
                            layer.openPopup();
                        }
                    });
                }
            });
        });
    }

    _buildCardHtml(p, index) {
        const trust = TRUST_COLORS[p.trust_label] || TRUST_COLORS['Unverified'];
        const hazard = HAZARD_ICONS[p.category] || HAZARD_ICONS['Unknown'];
        const clusterBadge = p.cluster_size > 1
            ? `<span class="cluster-badge">🔗 ${p.cluster_size} sources</span>` : '';
        const primarySource = (p.source_refs || [])[0];
        const animDelay = `${index * 40}ms`;

        return `
        <div class="news-card" style="animation-delay: ${animDelay}">
            ${p.image_url ? `
            <div class="news-card-img">
                <img src="${escapeHtml(p.image_url)}" alt="Disaster image"
                     onerror="this.parentElement.style.display='none'" />
            </div>` : ''}
            <div class="news-card-body">
                <!-- Tags row -->
                <div class="news-card-tags">
                    <span class="hazard-tag" style="background:${hazard.color}22;
                        color:${hazard.color}; border-color:${hazard.color}44;">
                        ${hazard.emoji} ${escapeHtml(p.category)}</span>
                    ${clusterBadge}
                    <span class="news-card-time">${timeAgo(p.published_at)}</span>
                </div>

                <!-- Title -->
                <div class="news-card-title">${escapeHtml(p.title)}</div>

                <!-- Location -->
                <div class="news-card-location">
                    📍 ${escapeHtml(p.location_name || '—')}
                </div>

                <!-- Trust Score Bar -->
                <div class="trust-bar-wrap">
                    <div class="trust-bar-header">
                        <span class="trust-label-text" style="color:${trust.text}">
                            ${trust.badge}
                        </span>
                        <span class="trust-score-num" style="color:${trust.text}">
                            ${formatScore(p.trust_score)}%
                        </span>
                    </div>
                    <div class="trust-bar-track">
                        <div class="trust-bar-fill" style="
                            width: ${formatScore(p.trust_score)}%;
                            background: linear-gradient(90deg, ${trust.border}88, ${trust.border});
                        "></div>
                    </div>
                    <div class="trust-breakdown">
                        <span>Authority: ${p.score_breakdown?.authority || 0}</span>
                        <span>Verified: ${p.score_breakdown?.verification || 0}</span>
                        <span>Media: ${p.score_breakdown?.completeness || 0}</span>
                        <span>Fresh: ${p.score_breakdown?.freshness || 0}</span>
                    </div>
                </div>

                <!-- Actions -->
                <div class="news-card-actions">
                    ${primarySource ? `
                    <a href="${escapeHtml(primarySource.url)}" target="_blank" rel="noopener"
                       class="news-card-btn news-card-btn-source">
                        🔗 Source
                    </a>` : ''}
                    <button class="news-card-btn news-card-btn-map"
                        data-lat="${p.lat || 0}"
                        data-lng="${p.lng || 0}"
                        data-cluster="${p.cluster_id}">
                        🗺️ View on Map
                    </button>
                </div>
            </div>
        </div>`;
    }

    // ── Status Bar ───────────────────────────────────────────────────────────

    _updateStatusBar(metadata) {
        if (!this.statusBarEl) return;
        const count = metadata?.item_count || 0;
        const generated = metadata?.generated_at
            ? new Date(metadata.generated_at).toLocaleTimeString() : '—';

        this.statusBarEl.innerHTML = `
            <span class="status-dot status-live"></span>
            <span class="status-text">LIVE</span>
            <span class="status-sep">|</span>
            <span>${count} active clusters</span>
            <span class="status-sep">|</span>
            <span>Updated ${generated}</span>
            <span class="status-sep">|</span>
            <span>Polls: ${this.totalPolls}</span>`;
        this.statusBarEl.classList.add('status-active');
    }

    _setStatusOffline() {
        if (!this.statusBarEl) return;
        this.statusBarEl.innerHTML = `
            <span class="status-dot status-offline"></span>
            <span>Connection lost — retrying in 10s</span>`;
        this.statusBarEl.classList.remove('status-active');
    }

    // ── Public Filter API ────────────────────────────────────────────────────

    filterByCategory(category) {
        this.currentFilter.category = category || null;
        if (this.geoJsonLayer) {
            // Re-render with new filter on next poll, or force now
            this._fetchAndRender();
        }
    }

    filterByMinTrust(minTrust) {
        this.currentFilter.minTrust = minTrust || null;
        this._fetchAndRender();
    }

    clearFilters() {
        this.currentFilter = { category: null, minTrust: null };
        this._fetchAndRender();
    }
}

// ─── Export for use in news_panel.html ───────────────────────────────────────
window.NewsLayerManager = NewsLayerManager;
window.NEWS_CONFIG = NEWS_CONFIG;
