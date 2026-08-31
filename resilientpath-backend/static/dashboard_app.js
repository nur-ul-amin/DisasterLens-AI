// NDMA NEOC Dashboard Application Logic — Pakistan National Coverage & Social/News Integration
// Handles Map Rendering, Spatial Clustering, Media Thumbnails & Verified Link Attachments

const API_BASE_URL = "/api/v1";
let map;
let markers;
let incidentData = []; // Store raw GeoJSON features

// Helper: Get stylized platform badge HTML
function getSourceBadgeHTML(sourceStr) {
    if (!sourceStr) return `<span class="source-tag tag-pwa">📱 PWA Field Report</span>`;
    
    if (sourceStr.includes("X (") || sourceStr.includes("Twitter")) {
        return `<span class="source-tag tag-x">𝕏 ${sourceStr}</span>`;
    } else if (sourceStr.includes("Facebook")) {
        return `<span class="source-tag tag-facebook">📘 ${sourceStr}</span>`;
    } else if (sourceStr.includes("Instagram")) {
        return `<span class="source-tag tag-instagram">📸 ${sourceStr}</span>`;
    } else if (sourceStr.includes("Dawn") || sourceStr.includes("Geo") || sourceStr.includes("News")) {
        return `<span class="source-tag tag-news">📰 ${sourceStr}</span>`;
    } else {
        return `<span class="source-tag tag-pwa">📱 ${sourceStr}</span>`;
    }
}

// Initialize the Map
function initMap() {
    // Bounds strictly encompassing Pakistan (Lat 23°N - 37°N, Lng 60°E - 78°E)
    const pakistanBounds = L.latLngBounds(
        L.latLng(23.0, 60.0),
        L.latLng(37.5, 78.0)
    );

    // Center on Pakistan
    map = L.map('neoc-map', {
        maxBounds: pakistanBounds,
        maxBoundsViscosity: 0.9,
        minZoom: 5
    }).setView([30.3753, 69.3451], 6);

    // Dark cartographic tiles suitable for command centers
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://carto.com/">CARTO</a> | NDMA Pakistan',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(map);

    // Initialize MarkerCluster group
    markers = L.markerClusterGroup({
        iconCreateFunction: function(cluster) {
            const count = cluster.getChildCount();
            let c = ' marker-cluster-';
            if (count < 10) {
                c += 'small';
            } else if (count < 50) {
                c += 'medium';
            } else {
                c += 'large';
            }
            return new L.DivIcon({ 
                html: '<div><span>' + count + '</span></div>', 
                className: 'marker-cluster' + c, 
                iconSize: new L.Point(40, 40) 
            });
        }
    });
    map.addLayer(markers);

    // Initial data fetch
    fetchIncidents();
    
    // Poll for new data every 5 seconds (Simulating WebSockets for PoC)
    setInterval(fetchIncidents, 5000);
}

// Fetch GeoJSON map layers from FastAPI
async function fetchIncidents() {
    try {
        const response = await fetch(`${API_BASE_URL}/reports/map-layers`);
        const data = await response.json();
        
        if (data && data.features) {
            incidentData = data.features;
            applyFilters(); // Renders the map and list
        }
    } catch (error) {
        console.error("Failed to fetch incident layers:", error);
    }
}

// Apply UI Filters to map and sidebar
function applyFilters() {
    const urgencyFilter = document.getElementById('filter-urgency').value;
    const passFilter = document.getElementById('filter-passability').value;
    const sourceFilterElem = document.getElementById('filter-source');
    const sourceFilter = sourceFilterElem ? sourceFilterElem.value : 'all';

    const filteredFeatures = incidentData.filter(feature => {
        const props = feature.properties;
        
        // Passability filter
        if (passFilter !== 'all' && props.passability_type !== passFilter) {
            return false;
        }

        // Urgency filter
        if (urgencyFilter === 'high' && props.urgency_score <= 80) return false;
        if (urgencyFilter === 'medium' && (props.urgency_score <= 50 || props.urgency_score > 80)) return false;
        if (urgencyFilter === 'low' && props.urgency_score > 50) return false;

        // Verified Source Platform Filter
        if (sourceFilter !== 'all') {
            const src = (props.source || '').toLowerCase();
            if (sourceFilter === 'X' && !src.includes('x') && !src.includes('twitter')) return false;
            if (sourceFilter === 'Facebook' && !src.includes('facebook')) return false;
            if (sourceFilter === 'Instagram' && !src.includes('instagram')) return false;
            if (sourceFilter === 'News' && !src.includes('dawn') && !src.includes('geo') && !src.includes('news')) return false;
            if (sourceFilter === 'PWA' && !src.includes('pwa')) return false;
        }

        return true;
    });

    renderMap(filteredFeatures);
    renderSidebar(filteredFeatures);
    updateStats(filteredFeatures);
}

// Render Spatial Markers on Map
function renderMap(features) {
    markers.clearLayers();

    features.forEach(feature => {
        const coords = feature.geometry.coordinates;
        const props = feature.properties;
        
        // Determine color based on urgency
        let color = '#10b981'; // Green (<50)
        if (props.urgency_score > 80) color = '#ef4444'; // Red (>80)
        else if (props.urgency_score > 50) color = '#f59e0b'; // Yellow (50-80)

        // Custom SVG Icon
        const svgIcon = L.divIcon({
            className: 'custom-div-icon',
            html: `<div style="background-color:${color}; width:18px; height:18px; border-radius:50%; border:2px solid white; box-shadow: 0 0 10px ${color};"></div>`,
            iconSize: [22, 22],
            iconAnchor: [11, 11]
        });

        const marker = L.marker([coords[1], coords[0]], { icon: svgIcon });
        
        // Image preview HTML if available
        const imgHTML = props.image_url 
            ? `<div class="popup-img-container"><img src="${props.image_url}" class="popup-img-thumb" alt="Disaster Evidence" onerror="this.style.display='none'" /></div>` 
            : '';

        // Source Link HTML if available
        const linkHTML = props.source_url 
            ? `<a href="${props.source_url}" target="_blank" rel="noopener noreferrer" class="btn-source-link">🔗 View Original Post / Article</a>` 
            : '';

        // Source Badge HTML
        const badgeHTML = getSourceBadgeHTML(props.source);

        // Popup Content
        const popupContent = `
            <div class="map-popup">
                <div class="popup-header">
                    <h4>${props.id}</h4>
                    <span class="popup-score" style="background-color:${color}22; color:${color}; border:1px solid ${color}">Urgency: ${props.urgency_score.toFixed(1)}</span>
                </div>
                <div class="popup-source-bar">${badgeHTML}</div>
                ${imgHTML}
                <div class="popup-body">
                    <p><strong>Raw Note:</strong> ${props.raw_text || 'No text provided'}</p>
                    <p><strong>Water Depth:</strong> ${props.water_depth}</p>
                    <p><strong>Passability:</strong> ${props.passability_type}</p>
                </div>
                <div class="popup-actions">
                    ${linkHTML}
                    <button onclick="verifyReport('${props.id}')" class="btn btn-sm ${props.verified_status ? 'btn-success' : 'btn-primary'}">
                        ${props.verified_status ? 'Verified ✓' : 'Verify Incident'}
                    </button>
                </div>
            </div>
        `;
        marker.bindPopup(popupContent);
        markers.addLayer(marker);
    });
}

// Render Event Stream in Sidebar
function renderSidebar(features) {
    const list = document.getElementById('incident-list');
    list.innerHTML = '';

    // Sort by Urgency (Highest first)
    const sorted = [...features].sort((a, b) => b.properties.urgency_score - a.properties.urgency_score);

    if (sorted.length === 0) {
        list.innerHTML = `<div class="no-data-text">No disaster reports matching active filters.</div>`;
        return;
    }

    sorted.slice(0, 50).forEach(feature => {
        const props = feature.properties;
        
        let urgencyClass = 'low';
        if (props.urgency_score > 80) urgencyClass = 'high';
        else if (props.urgency_score > 50) urgencyClass = 'medium';

        const badgeHTML = getSourceBadgeHTML(props.source);
        const imgThumb = props.image_url 
            ? `<img src="${props.image_url}" class="stream-img-thumb" alt="Flood Media" onerror="this.style.display='none'" />` 
            : '';

        const linkHTML = props.source_url 
            ? `<a href="${props.source_url}" target="_blank" rel="noopener noreferrer" class="stream-link" onclick="event.stopPropagation();">🔗 Open Link</a>` 
            : '';

        const item = document.createElement('div');
        item.className = `stream-item urgency-${urgencyClass}`;
        item.innerHTML = `
            <div class="stream-item-header">
                <span class="stream-id">${props.id}</span>
                <span class="stream-score">${props.urgency_score.toFixed(1)}</span>
            </div>
            <div class="stream-source-row">${badgeHTML}</div>
            <div class="stream-content-wrapper">
                ${imgThumb}
                <div class="stream-text-details">
                    <div class="stream-body">${props.raw_text ? props.raw_text : props.water_depth + ' - ' + props.passability_type}</div>
                    <div class="stream-meta-info">
                        <span class="meta-tag">💧 ${props.water_depth}</span>
                        <span class="meta-tag">🚗 ${props.passability_type}</span>
                    </div>
                </div>
            </div>
            <div class="stream-footer">
                <span class="stream-time">🕒 ${props.created_at ? new Date(props.created_at).toLocaleTimeString() : 'Just now'}</span>
                ${linkHTML}
                <span class="${props.verified_status ? 'text-success' : 'text-warning'}">
                    ${props.verified_status ? 'VERIFIED ✓' : 'UNVERIFIED'}
                </span>
            </div>
        `;
        
        // Click to zoom on map
        item.onclick = () => {
            const coords = feature.geometry.coordinates;
            map.flyTo([coords[1], coords[0]], 13, { duration: 1.2 });
        };
        
        list.appendChild(item);
    });
}

function updateStats(features) {
    document.getElementById('stat-active').textContent = features.length;
    document.getElementById('stat-critical').textContent = features.filter(f => f.properties.urgency_score > 80).length;
}

// Action: Verify Report via FastAPI
async function verifyReport(id) {
    try {
        await fetch(`${API_BASE_URL}/reports/${id}/verify`, { method: 'POST' });
        fetchIncidents(); // Refresh UI
    } catch (error) {
        alert("Verification failed.");
    }
}

// Action: Export Data
function exportData(format) {
    if (format === 'geojson') {
        const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({ type: "FeatureCollection", features: incidentData }));
        const dlAnchorElem = document.createElement('a');
        dlAnchorElem.setAttribute("href", dataStr);
        dlAnchorElem.setAttribute("download", `ndma_pakistan_disaster_export_${Date.now()}.geojson`);
        dlAnchorElem.click();
    } else {
        alert("CSV Export not implemented in PoC. Use GeoJSON.");
    }
}

// Boot
window.onload = initMap;
