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
// New feature modules for web dashboard

// Community Reports Module
const communityReports = {
    activeReports: new Map(),
    
    async submitReport(type, message, location, photo = null) {
        try {
            const response = await fetch(`${API_BASE_URL}/community/report?user_id=web-user`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    latitude: location.lat,
                    longitude: location.lng,
                    report_type: type,
                    message: message,
                    photo_base64: photo,
                    expires_in_minutes: 30
                })
            });
            
            if (response.ok) {
                const result = await response.json();
                showSuccess('Report submitted successfully!');
                await this.loadNearbyReports(location);
                return result;
            }
        } catch (error) {
            console.error('Failed to submit report:', error);
            showError('Failed to submit report');
        }
    },
    
    async loadNearbyReports(location) {
        try {
            const response = await fetch(
                `${API_BASE_URL}/community/reports?lat=${location.lat}&lon=${location.lng}&radius_meters=500`
            );
            
            if (response.ok) {
                const reports = await response.json();
                this.displayReports(reports);
            }
        } catch (error) {
            console.error('Failed to load reports:', error);
        }
    },
    
    displayReports(reports) {
        // Clear existing report markers
        this.activeReports.forEach(marker => state.map.removeLayer(marker));
        this.activeReports.clear();
        
        reports.forEach(report => {
            const icon = this.getReportIcon(report.type);
            const marker = L.marker([report.latitude, report.longitude], { icon })
                .bindPopup(`
                    <div class="report-popup">
                        <strong>${this.getReportTitle(report.type)}</strong><br>
                        ${report.message}<br>
                        <small>${this.getTimeAgo(report.created_at)}</small><br>
                        <small>👍 ${report.upvotes}</small>
                    </div>
                `)
                .addTo(state.map);
                
            this.activeReports.set(report.id, marker);
        });
    },
    
    getReportIcon(type) {
        const icons = {
            'spot_available': '🟢',
            'spot_taken': '🔴',
            'ticket_officer': '👮',
            'construction': '🚧'
        };
        
        return L.divIcon({
            html: `<div class="report-icon">${icons[type] || '📍'}</div>`,
            className: 'custom-div-icon',
            iconSize: [30, 30],
            iconAnchor: [15, 15]
        });
    },
    
    getReportTitle(type) {
        const titles = {
            'spot_available': 'Parking Available',
            'spot_taken': 'Spot Taken',
            'ticket_officer': 'Enforcement Alert',
            'construction': 'Construction Zone'
        };
        return titles[type] || 'Community Report';
    },
    
    getTimeAgo(timestamp) {
        const now = new Date();
        const then = new Date(timestamp);
        const diffMs = now - then;
        const diffMins = Math.floor(diffMs / 60000);
        
        if (diffMins < 1) return 'just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
        return `${Math.floor(diffMins / 1440)}d ago`;
    }
};

// Parking Timer Module
const parkingTimer = {
    activeTimer: null,
    timerInterval: null,
    
    async startTimer(duration, location, notes = '') {
        try {
            const response = await fetch(`${API_BASE_URL}/parking/timer?user_id=web-user`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    duration_minutes: duration,
                    latitude: location.lat,
                    longitude: location.lng,
                    reminder_before: 15,
                    notes: notes
                })
            });
            
            if (response.ok) {
                const timer = await response.json();
                this.activeTimer = timer;
                this.startCountdown(timer.expires_at);
                showSuccess(`Timer set for ${duration} minutes`);
                return timer;
            }
        } catch (error) {
            console.error('Failed to set timer:', error);
            showError('Failed to set parking timer');
        }
    },
    
    startCountdown(expiresAt) {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }
        
        this.timerInterval = setInterval(() => {
            const now = new Date();
            const expiry = new Date(expiresAt);
            const remaining = expiry - now;
            
            if (remaining <= 0) {
                this.timerExpired();
            } else {
                this.updateTimerDisplay(remaining);
                
                // Check for reminder
                if (remaining <= 15 * 60 * 1000 && remaining > 14 * 60 * 1000) {
                    this.showReminder();
                }
            }
        }, 1000);
    },
    
    updateTimerDisplay(remaining) {
        const hours = Math.floor(remaining / 3600000);
        const minutes = Math.floor((remaining % 3600000) / 60000);
        const seconds = Math.floor((remaining % 60000) / 1000);
        
        const display = document.getElementById('timerDisplay');
        if (display) {
            display.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }
    },
    
    showReminder() {
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification('Parking Timer Reminder', {
                body: 'Your parking expires in 15 minutes!',
                icon: '/icon.png',
                requireInteraction: true
            });
        }
        
        showWarning('Your parking expires in 15 minutes!');
        
        // Play sound if enabled
        const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBSuBzvLZiTYIG2m98OScTgwOUarm7blmFgU7k9n1yHUoBCh+zPLaizsIGGW57+6lVBQKSKPj8LptIAcmd8jz2olLMA');
        audio.play();
    },
    
    timerExpired() {
        clearInterval(this.timerInterval);
        this.activeTimer = null;
        
        showError('Parking timer expired!');
        
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification('Parking Expired!', {
                body: 'Your parking time has expired. Please move your vehicle.',
                icon: '/icon.png',
                requireInteraction: true
            });
        }
    },
    
    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }
        this.activeTimer = null;
        document.getElementById('timerDisplay').textContent = '--:--:--';
    }
};

// Favorite Spots Module
const favoriteSpots = {
    favorites: new Map(),
    
    async addFavorite(name, location, notes = '') {
        try {
            const response = await fetch(`${API_BASE_URL}/users/favorites?user_id=web-user`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: name,
                    latitude: location.lat,
                    longitude: location.lng,
                    notes: notes
                })
            });
            
            if (response.ok) {
                const result = await response.json();
                showSuccess('Favorite spot saved!');
                await this.loadFavorites();
                return result;
            }
        } catch (error) {
            console.error('Failed to save favorite:', error);
            showError('Failed to save favorite spot');
        }
    },
    
    async loadFavorites() {
        try {
            const response = await fetch(`${API_BASE_URL}/users/favorites?user_id=web-user`);
            
            if (response.ok) {
                const favorites = await response.json();
                this.displayFavorites(favorites);
            }
        } catch (error) {
            console.error('Failed to load favorites:', error);
        }
    },
    
    displayFavorites(favorites) {
        const container = document.getElementById('favoritesList');
        if (!container) return;
        
        container.innerHTML = '<h4>Favorite Spots</h4>';
        
        favorites.forEach(fav => {
            const div = document.createElement('div');
            div.className = 'favorite-item';
            div.innerHTML = `
                <span class="favorite-icon">⭐</span>
                <div class="favorite-info">
                    <strong>${fav.name}</strong><br>
                    <small>${fav.street_name || 'Unknown street'}</small><br>
                    <small>Success rate: ${Math.round(fav.success_rate * 100)}%</small>
                    ${fav.notes ? `<br><small>${fav.notes}</small>` : ''}
                </div>
                <button onclick="navigateToFavorite('${fav.id}')" class="navigate-btn">Go</button>
            `;
            
            container.appendChild(div);
            
            // Store for navigation
            this.favorites.set(fav.id, fav);
        });
    },
    
    navigateTo(favoriteId) {
        const fav = this.favorites.get(favoriteId);
        if (fav) {
            state.map.setView([fav.latitude, fav.longitude], 17);
            setMarker(fav.latitude, fav.longitude);
            fetchParkingData(fav.latitude, fav.longitude);
        }
    }
};

// Parking Predictions Module
const parkingPredictions = {
    async getPredictions(location, targetTime) {
        try {
            const response = await fetch(
                `${API_BASE_URL}/parking/predictions?` +
                `lat=${location.lat}&lon=${location.lng}&` +
                `target_time=${targetTime.toISOString()}`
            );
            
            if (response.ok) {
                const predictions = await response.json();
                this.displayPredictions(predictions);
                return predictions;
            }
        } catch (error) {
            console.error('Failed to get predictions:', error);
        }
    },
    
    displayPredictions(predictions) {
        const container = document.getElementById('predictionsList');
        if (!container || !predictions.length) return;
        
        container.innerHTML = '<h4>Parking Predictions</h4>';
        
        predictions.forEach(pred => {
            const probability = Math.round(pred.availability_probability * 100);
            const color = probability > 70 ? 'green' : probability > 40 ? 'orange' : 'red';
            
            const div = document.createElement('div');
            div.className = 'prediction-item';
            div.innerHTML = `
                <div class="prediction-chart">
                    <div class="prediction-bar" style="width: ${probability}%; background-color: ${color}"></div>
                </div>
                <div class="prediction-info">
                    <strong>${probability}% chance of finding parking</strong><br>
                    <small>${this.formatTime(pred.target_time)}</small><br>
                    <small>${pred.recommendation}</small>
                </div>
            `;
            
            container.appendChild(div);
        });
    },
    
    formatTime(isoString) {
        const date = new Date(isoString);
        return date.toLocaleString('en-US', {
            weekday: 'short',
            hour: 'numeric',
            minute: '2-digit'
        });
    }
};

// Garage Comparison Module
const garageComparison = {
    garages: [],
    
    async loadNearbyGarages(location) {
        try {
            const response = await fetch(
                `${API_BASE_URL}/garages/nearby?` +
                `lat=${location.lat}&lon=${location.lng}&radius_meters=500`
            );
            
            if (response.ok) {
                this.garages = await response.json();
                this.displayGarages();
            }
        } catch (error) {
            console.error('Failed to load garages:', error);
        }
    },
    
    displayGarages() {
        const container = document.getElementById('garagesList');
        if (!container || !this.garages.length) return;
        
        container.innerHTML = '<h4>Nearby Garages</h4>';
        
        this.garages.forEach(garage => {
            const div = document.createElement('div');
            div.className = 'garage-item';
            
            const availabilityClass = garage.availability === 'available' ? 'available' : 
                                     garage.availability === 'limited' ? 'limited' : 'full';
            
            div.innerHTML = `
                <div class="garage-header">
                    <strong>${garage.name}</strong>
                    <span class="garage-distance">${garage.distance_meters}m</span>
                </div>
                <div class="garage-price">
                    $${garage.price_per_hour}/hr | $${garage.price_per_day}/day
                </div>
                <div class="garage-availability ${availabilityClass}">
                    ${garage.available_spots}/${garage.total_spots} spots
                </div>
                <div class="garage-features">
                    ${garage.features.map(f => `<span class="feature-tag">${f}</span>`).join('')}
                </div>
                <button onclick="navigateToGarage('${garage.id}')" class="garage-nav-btn">
                    Navigate
                </button>
            `;
            
            container.appendChild(div);
        });
    },
    
    navigateToGarage(garageId) {
        const garage = this.garages.find(g => g.id === garageId);
        if (garage && garage.entrance_location) {
            // Open in navigation app
            const url = `https://maps.google.com/maps?daddr=${garage.entrance_location.latitude},${garage.entrance_location.longitude}`;
            window.open(url, '_blank');
        }
    }
};

// Initialize new features
function initializeFeatures() {
    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }
    
    // Load initial data
    if (state.currentLocation) {
        communityReports.loadNearbyReports(state.currentLocation);
        favoriteSpots.loadFavorites();
        garageComparison.loadNearbyGarages(state.currentLocation);
    }
    
    // Add event listeners for new features
    setupFeatureUI();
}

// Helper functions for UI feedback
function showSuccess(message) {
    showNotification(message, 'success');
}

function showWarning(message) {
    showNotification(message, 'warning');
}

function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => notification.classList.add('show'), 10);
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Add to window for global access
window.communityReports = communityReports;
window.parkingTimer = parkingTimer;
window.favoriteSpots = favoriteSpots;
window.parkingPredictions = parkingPredictions;
window.garageComparison = garageComparison;
window.navigateToFavorite = (id) => favoriteSpots.navigateTo(id);
window.navigateToGarage = (id) => garageComparison.navigateToGarage(id);

// Call this after map initialization
window.addEventListener('DOMContentLoaded', function() {
    // Existing initialization...
    
    // Initialize new features
    setTimeout(initializeFeatures, 1000);
});
// Helper functions for new features
function submitReport() {
    const type = document.getElementById('reportType').value;
    const message = document.getElementById('reportMessage').value;
    
    if (!message.trim()) {
        showError('Please add details to your report');
        return;
    }
    
    communityReports.submitReport(type, message, state.currentLocation);
    
    // Clear form
    document.getElementById('reportMessage').value = '';
}

function addCurrentLocationAsFavorite() {
    const name = prompt('Name this favorite spot:');
    if (name) {
        favoriteSpots.addFavorite(name, state.currentLocation);
    }
}

function getPredictions() {
    const timeInput = document.getElementById('predictionTime').value;
    if (!timeInput) {
        showError('Please select a target time');
        return;
    }
    
    const targetTime = new Date(timeInput);
    parkingPredictions.getPredictions(state.currentLocation, targetTime);
}

// Setup additional UI elements
function setupFeatureUI() {
    // Set default prediction time to 1 hour from now
    const futureTime = new Date();
    futureTime.setHours(futureTime.getHours() + 1);
    futureTime.setMinutes(0);
    const timeString = futureTime.toISOString().slice(0, 16);
    document.getElementById('predictionTime').value = timeString;
    
    // Add real-time community report updates
    setInterval(() => {
        if (state.currentLocation) {
            communityReports.loadNearbyReports(state.currentLocation);
        }
    }, 60000); // Update every minute
}

// Audio navigation simulation for web
let audioEnabled = false;
let lastAudioStreet = null;
let audioSimInterval = null;

function toggleAudioNavigation() {
    audioEnabled = !audioEnabled;
    const button = document.querySelector('.audio-toggle');
    
    if (audioEnabled) {
        button.classList.add('active');
        speakText('Audio navigation enabled');
        
        // Simulate audio updates when tracking
        if (state.isTracking) {
            startAudioSimulation();
        }
    } else {
        button.classList.remove('active');
        speakText('Audio navigation disabled');
        stopAudioSimulation();
    }
}

function startAudioSimulation() {
    if (!audioEnabled || audioSimInterval) return;
    
    // Simulate street change detection
    audioSimInterval = setInterval(async () => {
        if (!state.currentLocation || !audioEnabled) return;
        
        try {
            const response = await fetch(`${API_BASE_URL}/audio/navigation`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    location: {
                        latitude: state.currentLocation.lat,
                        longitude: state.currentLocation.lng
                    },
                    heading: 0, // Would come from device compass
                    speed: state.currentSpeed || 0
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                
                if (data.current_announcement && data.should_announce) {
                    speakText(data.current_announcement.text);
                }
                
                // Handle predictive announcements
                if (data.predictive_announcement && data.predictive_announcement.priority >= 3) {
                    setTimeout(() => {
                        speakText(data.predictive_announcement.text);
                    }, 3000);
                }
            }
        } catch (error) {
            console.error('Audio navigation error:', error);
        }
    }, 5000); // Check every 5 seconds
}

function stopAudioSimulation() {
    if (audioSimInterval) {
        clearInterval(audioSimInterval);
        audioSimInterval = null;
    }
}

// Text-to-speech function
function speakText(text) {
    if (!audioEnabled || !text) return;
    
    // Use Web Speech API
    if ('speechSynthesis' in window) {
        // Cancel any ongoing speech
        speechSynthesis.cancel();
        
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 0.8;
        utterance.lang = 'en-US';
        
        // Add visual feedback
        const audioButton = document.querySelector('.audio-toggle');
        utterance.onstart = () => {
            audioButton.style.animation = 'pulse 1s infinite';
        };
        
        utterance.onend = () => {
            audioButton.style.animation = '';
        };
        
        speechSynthesis.speak(utterance);
        
        // Also show as notification
        showNotification(`🔊 ${text}`, 'info');
    }
}

// Add pulse animation for audio button
const style = document.createElement('style');
style.textContent = `
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.1); }
        100% { transform: scale(1); }
    }
`;
document.head.appendChild(style);

// Update tracking functions to support audio
const originalStartTracking = startTracking;
startTracking = function() {
    originalStartTracking();
    if (audioEnabled) {
        startAudioSimulation();
    }
};

const originalStopTracking = stopTracking;
stopTracking = function() {
    originalStopTracking();
    stopAudioSimulation();
};

// Offline support
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').then(registration => {
        console.log('Service Worker registered');
    }).catch(error => {
        console.log('Service Worker registration failed:', error);
    });
}

// Export new functions
window.submitReport = submitReport;
window.addCurrentLocationAsFavorite = addCurrentLocationAsFavorite;
window.getPredictions = getPredictions;
window.toggleAudioNavigation = toggleAudioNavigation;
window.speakText = speakText;