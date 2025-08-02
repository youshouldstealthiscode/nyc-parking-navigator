// NYC Parking Navigator Dashboard - Optimized
const API_BASE_URL = 'http://localhost:8000/api/v1';

// Global state management
const state = {
    map: null,
    currentMarker: null,
    userMarker: null,
    parkingOverlays: [],
    currentLocation: { lat: 40.7580, lng: -73.9855 },
    isTracking: false,
    watchId: null,
    lastFetchTime: null,
    cache: new Map()
};

// Cache configuration
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

// Debounce function for performance
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Throttle function for rate limiting
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Initialize map with error handling
async function initMap() {
    try {
        state.map = L.map('map', {
            center: [state.currentLocation.lat, state.currentLocation.lng],
            zoom: 15,
            zoomControl: true,
            attributionControl: true
        });
        
        // Add tile layer with fallback
        const tileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19,
            errorTileUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='
        });
        
        tileLayer.on('tileerror', function(error, tile) {
            console.warn('Tile loading error:', error);
        });
        
        tileLayer.addTo(state.map);
        
        // Add click handler with debouncing
        state.map.on('click', debounce(onMapClick, 300));
        
        // Set current time in time selector
        const now = new Date();
        now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
        document.getElementById('queryTime').value = now.toISOString().slice(0, 16);
        
        // Initial load with error handling
        await updateParkingDisplay();
        
        // Setup periodic cache cleanup
        setInterval(cleanupCache, 60000); // Every minute
        
    } catch (error) {
        console.error('Failed to initialize map:', error);
        showError('Failed to initialize map. Please refresh the page.');
    }
}

// Cache management
function getCacheKey(lat, lng, radius, time) {
    return `${lat.toFixed(4)}_${lng.toFixed(4)}_${radius}_${time || 'current'}`;
}

function getFromCache(key) {
    const cached = state.cache.get(key);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
        return cached.data;
    }
    state.cache.delete(key);
    return null;
}

function setCache(key, data) {
    state.cache.set(key, {
        data: data,
        timestamp: Date.now()
    });
}

function cleanupCache() {
    const now = Date.now();
    for (const [key, value] of state.cache.entries()) {
        if (now - value.timestamp > CACHE_TTL) {
            state.cache.delete(key);
        }
    }
}

// Error handling and user feedback
function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.innerHTML = `
        <strong>Error:</strong> ${message}
        <button onclick="this.parentElement.remove()">×</button>
    `;
    document.body.appendChild(errorDiv);
    
    setTimeout(() => errorDiv.remove(), 5000);
}

function showLoading(show) {
    const loader = document.getElementById('loader');
    if (loader) {
        loader.style.display = show ? 'block' : 'none';
    }
}
// Handle map clicks with rate limiting
const onMapClick = throttle(async function(e) {
    const { lat, lng } = e.latlng;
    setMarker(lat, lng);
    await fetchParkingData(lat, lng);
}, 1000);

// Set marker on map
function setMarker(lat, lng) {
    if (state.currentMarker) {
        state.map.removeLayer(state.currentMarker);
    }
    
    state.currentMarker = L.marker([lat, lng], {
        icon: L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
        })
    }).addTo(state.map);
    
    state.currentLocation = { lat, lng };
}

// Fetch parking data with caching and error handling
async function fetchParkingData(lat, lng, radius = 300) {
    const queryTime = document.getElementById('queryTime').value;
    const cacheKey = getCacheKey(lat, lng, radius, queryTime);
    
    // Check cache first
    const cached = getFromCache(cacheKey);
    if (cached) {
        console.log('Using cached data');
        displayParkingSegments(cached);
        return;
    }
    
    showLoading(true);
    
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10s timeout
        
        const response = await fetch(`${API_BASE_URL}/parking/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                location: { latitude: lat, longitude: lng },
                radius_meters: radius,
                query_time: queryTime ? new Date(queryTime).toISOString() : null
            }),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error?.message || `HTTP error! status: ${response.status}`);
        }
        
        const segments = await response.json();
        
        // Cache the results
        setCache(cacheKey, segments);
        
        displayParkingSegments(segments);
        state.lastFetchTime = Date.now();
        
    } catch (error) {
        console.error('Error fetching parking data:', error);
        
        if (error.name === 'AbortError') {
            showError('Request timed out. Please try again.');
        } else {
            showError('Failed to fetch parking data. Please check your connection.');
        }
    } finally {
        showLoading(false);
    }
}

// Display parking segments with performance optimizations
function displayParkingSegments(segments) {
    // Clear existing overlays efficiently
    if (state.parkingOverlays.length > 0) {
        const layerGroup = L.layerGroup(state.parkingOverlays);
        state.map.removeLayer(layerGroup);
        state.parkingOverlays = [];
    }
    
    // Clear segment list
    const segmentList = document.getElementById('segmentList');
    segmentList.innerHTML = '<h3>Parking Segments</h3>';
    
    // Use document fragment for better performance
    const fragment = document.createDocumentFragment();
    
    // Process segments in batches for better performance
    const batchSize = 50;
    let currentBatch = 0;
    
    function processBatch() {
        const start = currentBatch * batchSize;
        const end = Math.min(start + batchSize, segments.length);
        
        for (let i = start; i < end; i++) {
            const segment = segments[i];
            
            // Draw on map
            if (segment.coordinates && segment.coordinates.length > 0) {
                const coordinates = segment.coordinates.map(coord => [coord[1], coord[0]]);
                const color = getColorForStatus(segment.status_color);
                
                const polyline = L.polyline(coordinates, {
                    color: color,
                    weight: 6,
                    opacity: 0.8,
                    smoothFactor: 1
                });
                
                // Add popup with lazy loading
                polyline.bindPopup(() => createPopupContent(segment), {
                    maxWidth: 300,
                    className: 'parking-popup'
                });
                
                polyline.addTo(state.map);
                state.parkingOverlays.push(polyline);
            }
            
            // Add to list
            const segmentDiv = createSegmentElement(segment);
            fragment.appendChild(segmentDiv);
        }
        
        currentBatch++;
        
        if (end < segments.length) {
            // Process next batch asynchronously
            requestAnimationFrame(processBatch);
        } else {
            // All done, update DOM once
            segmentList.appendChild(fragment);
            
            // Fit map to bounds if segments exist
            if (state.parkingOverlays.length > 0) {
                const group = L.featureGroup(state.parkingOverlays);
                state.map.fitBounds(group.getBounds().pad(0.1));
            }
            
            updateStatistics(segments);
        }
    }
    
    processBatch();
}

// Create popup content lazily
function createPopupContent(segment) {
    const regulations = segment.regulations
        .map(r => r.description || '')
        .filter(r => r)
        .join('<br>');
        
    return `
        <div class="popup-content">
            <strong>${segment.street_name}</strong><br>
            <span class="popup-side">Side: ${segment.side}</span><br>
            <span class="popup-status status-${segment.status_color}">
                Status: ${segment.current_status}
            </span><br>
            ${regulations ? `<div class="popup-regulations">${regulations}</div>` : ''}
            ${segment.confidence_score ? `<small>Confidence: ${Math.round(segment.confidence_score * 100)}%</small>` : ''}
        </div>
    `;
}

// Create segment element efficiently
function createSegmentElement(segment) {
    const div = document.createElement('div');
    div.className = 'segment-info';
    div.innerHTML = `
        <span class="status-indicator status-${segment.status_color}"></span>
        <strong>${segment.street_name}</strong> - ${segment.side} side<br>
        Status: ${segment.current_status}
        ${segment.next_change ? `<br>Next change: ${new Date(segment.next_change).toLocaleString()}` : ''}
        ${segment.distance ? `<br>Distance: ${Math.round(segment.distance)}m` : ''}
    `;
    
    // Add click handler to zoom to segment
    div.addEventListener('click', () => {
        if (segment.coordinates && segment.coordinates.length > 0) {
            const center = segment.coordinates[Math.floor(segment.coordinates.length / 2)];
            state.map.setView([center[1], center[0]], 18);
        }
    });
    
    return div;
}
// Update statistics panel
function updateStatistics(segments) {
    const stats = {
        total: segments.length,
        available: 0,
        restricted: 0,
        metered: 0
    };
    
    segments.forEach(segment => {
        switch (segment.status_color) {
            case 'green': stats.available++; break;
            case 'red': stats.restricted++; break;
            case 'blue': stats.metered++; break;
        }
    });
    
    // Update stats display if exists
    const statsDiv = document.getElementById('parkingStats');
    if (statsDiv) {
        statsDiv.innerHTML = `
            <h4>Parking Statistics</h4>
            <div class="stat-item">Total Segments: ${stats.total}</div>
            <div class="stat-item">
                <span class="status-indicator status-green"></span>
                Available: ${stats.available} (${Math.round(stats.available/stats.total*100)}%)
            </div>
            <div class="stat-item">
                <span class="status-indicator status-red"></span>
                Restricted: ${stats.restricted} (${Math.round(stats.restricted/stats.total*100)}%)
            </div>
            <div class="stat-item">
                <span class="status-indicator status-blue"></span>
                Metered: ${stats.metered} (${Math.round(stats.metered/stats.total*100)}%)
            </div>
        `;
    }
}

// Get color for parking status
function getColorForStatus(statusColor) {
    const colors = {
        'green': '#4CAF50',
        'red': '#f44336',
        'blue': '#2196F3',
        'yellow': '#FFEB3B',
        'gray': '#9E9E9E'
    };
    return colors[statusColor] || colors.gray;
}

// Search address with validation
async function searchAddress() {
    const addressInput = document.getElementById('addressInput');
    const address = addressInput.value.trim();
    
    if (!address) {
        showError('Please enter an address');
        return;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch(
            `https://nominatim.openstreetmap.org/search?` +
            `q=${encodeURIComponent(address + ', New York, NY')}&format=json&limit=1`,
            {
                headers: {
                    'User-Agent': 'NYC-Parking-Navigator/1.0'
                }
            }
        );
        
        if (!response.ok) {
            throw new Error('Geocoding service error');
        }
        
        const results = await response.json();
        
        if (results.length > 0) {
            const { lat, lon } = results[0];
            state.map.setView([lat, lon], 17);
            setMarker(lat, lon);
            await fetchParkingData(lat, lon);
            
            // Clear input on success
            addressInput.value = '';
        } else {
            showError('Address not found. Please try a more specific address.');
        }
    } catch (error) {
        console.error('Error searching address:', error);
        showError('Failed to search address. Please try again.');
    } finally {
        showLoading(false);
    }
}

// Use current location with error handling
function useCurrentLocation() {
    if (!navigator.geolocation) {
        showError('Geolocation is not supported by your browser');
        return;
    }
    
    showLoading(true);
    
    navigator.geolocation.getCurrentPosition(
        async position => {
            const { latitude, longitude } = position.coords;
            state.map.setView([latitude, longitude], 17);
            setMarker(latitude, longitude);
            await fetchParkingData(latitude, longitude);
            showLoading(false);
        },
        error => {
            showLoading(false);
            
            switch (error.code) {
                case error.PERMISSION_DENIED:
                    showError('Location permission denied. Please enable location access.');
                    break;
                case error.POSITION_UNAVAILABLE:
                    showError('Location information unavailable.');
                    break;
                case error.TIMEOUT:
                    showError('Location request timed out.');
                    break;
                default:
                    showError('An unknown error occurred getting your location.');
            }
        },
        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        }
    );
}

// Toggle location tracking
function toggleTracking() {
    const button = document.getElementById('trackingButton');
    
    if (!state.isTracking) {
        startTracking();
        button.textContent = 'Stop Following';
        button.style.background = '#f44336';
    } else {
        stopTracking();
        button.textContent = 'Follow My Location';
        button.style.background = '#4CAF50';
    }
    state.isTracking = !state.isTracking;
}

// Start continuous location tracking
function startTracking() {
    if (!navigator.geolocation) {
        showError('Geolocation is not supported');
        return;
    }
    
    // Clear any existing watch
    if (state.watchId) {
        navigator.geolocation.clearWatch(state.watchId);
    }
    
    state.watchId = navigator.geolocation.watchPosition(
        async position => {
            const { latitude, longitude, accuracy } = position.coords;
            
            // Update user marker
            if (state.userMarker) {
                state.userMarker.setLatLng([latitude, longitude]);
                state.userMarker.setRadius(accuracy);
            } else {
                // Create user marker with accuracy circle
                state.userMarker = L.circleMarker([latitude, longitude], {
                    radius: 8,
                    fillColor: '#4285F4',
                    color: '#fff',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.8
                }).addTo(state.map);
                
                // Add accuracy circle
                L.circle([latitude, longitude], {
                    radius: accuracy,
                    color: '#4285F4',
                    fillColor: '#4285F4',
                    fillOpacity: 0.1,
                    weight: 1
                }).addTo(state.map);
            }
            
            // Center map on user
            state.map.setView([latitude, longitude], state.map.getZoom(), {
                animate: true,
                duration: 0.5
            });
            
            // Auto-fetch parking data if in NYC and enough time has passed
            if (latitude > 40.4 && latitude < 41.0 && 
                longitude > -74.3 && longitude < -73.7) {
                
                const timeSinceLastFetch = Date.now() - (state.lastFetchTime || 0);
                if (timeSinceLastFetch > 30000) { // 30 seconds
                    await fetchParkingData(latitude, longitude);
                }
            }
        },
        error => {
            console.error('Tracking error:', error);
            showError('Lost GPS signal. Tracking paused.');
            
            // Don't stop tracking, just wait for signal to return
        },
        {
            enableHighAccuracy: true,
            maximumAge: 0,
            timeout: 5000
        }
    );
}

// Stop tracking
function stopTracking() {
    if (state.watchId) {
        navigator.geolocation.clearWatch(state.watchId);
        state.watchId = null;
    }
    
    // Remove user marker
    if (state.userMarker) {
        state.map.removeLayer(state.userMarker);
        state.userMarker = null;
    }
}

// Update parking display
async function updateParkingDisplay() {
    if (state.currentLocation.lat && state.currentLocation.lng) {
        await fetchParkingData(state.currentLocation.lat, state.currentLocation.lng);
    }
}

// Add keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + F for search
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault();
        document.getElementById('addressInput').focus();
    }
    
    // Escape to cancel search
    if (e.key === 'Escape') {
        document.getElementById('addressInput').blur();
    }
});

// Handle online/offline status
window.addEventListener('online', () => {
    console.log('Connection restored');
    updateParkingDisplay();
});

window.addEventListener('offline', () => {
    showError('You are offline. Some features may not work.');
});

// Initialize on load with error boundary
window.addEventListener('DOMContentLoaded', function() {
    try {
        initMap();
    } catch (error) {
        console.error('Failed to initialize application:', error);
        document.body.innerHTML = `
            <div class="error-page">
                <h1>Failed to Load</h1>
                <p>Sorry, the application failed to initialize.</p>
                <button onclick="location.reload()">Reload Page</button>
            </div>
        `;
    }
});