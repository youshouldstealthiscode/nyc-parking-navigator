// NYC Parking Navigator Dashboard
const API_BASE_URL = 'http://localhost:8000';

let map;
let currentMarker;
let parkingOverlays = [];
let currentLocation = { lat: 40.7580, lng: -73.9855 }; // Times Square default

// Initialize map
function initMap() {
    map = L.map('map').setView([currentLocation.lat, currentLocation.lng], 15);
    
    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
    
    // Add click handler
    map.on('click', onMapClick);
    
    // Set current time in time selector
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    document.getElementById('queryTime').value = now.toISOString().slice(0, 16);
    
    // Initial load
    updateParkingDisplay();
}

// Handle map clicks
function onMapClick(e) {
    const { lat, lng } = e.latlng;
    setMarker(lat, lng);
    fetchParkingData(lat, lng);
}

// Set marker on map
function setMarker(lat, lng) {
    if (currentMarker) {
        map.removeLayer(currentMarker);
    }
    
    currentMarker = L.marker([lat, lng]).addTo(map);
    currentLocation = { lat, lng };
}
// Fetch parking data from API
async function fetchParkingData(lat, lng, radius = 300) {
    try {
        const queryTime = document.getElementById('queryTime').value;
        
        const response = await fetch(`${API_BASE_URL}/parking/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                location: { latitude: lat, longitude: lng },
                radius_meters: radius,
                query_time: queryTime ? new Date(queryTime).toISOString() : null
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const segments = await response.json();
        displayParkingSegments(segments);
        
    } catch (error) {
        console.error('Error fetching parking data:', error);
        alert('Error fetching parking data. Make sure the backend is running.');
    }
}

// Display parking segments on map
function displayParkingSegments(segments) {
    // Clear existing overlays
    parkingOverlays.forEach(overlay => map.removeLayer(overlay));
    parkingOverlays = [];
    
    // Clear segment list
    const segmentList = document.getElementById('segmentList');
    segmentList.innerHTML = '<h3>Parking Segments</h3>';
    
    // Add new segments
    segments.forEach(segment => {
        // Draw on map
        const coordinates = segment.coordinates.map(coord => [coord[1], coord[0]]);
        const color = getColorForStatus(segment.status_color);
        
        const polyline = L.polyline(coordinates, {
            color: color,
            weight: 6,
            opacity: 0.8
        }).addTo(map);
        
        parkingOverlays.push(polyline);
        // Add popup
        polyline.bindPopup(`
            <strong>${segment.street_name}</strong><br>
            Side: ${segment.side}<br>
            Status: ${segment.current_status}<br>
            ${segment.regulations.map(r => r.description || '').join('<br>')}
        `);
        
        // Add to list
        const segmentDiv = document.createElement('div');
        segmentDiv.className = 'segment-info';
        segmentDiv.innerHTML = `
            <span class="status-indicator status-${segment.status_color}"></span>
            <strong>${segment.street_name}</strong> - ${segment.side} side<br>
            Status: ${segment.current_status}
            ${segment.next_change ? `<br>Next change: ${new Date(segment.next_change).toLocaleString()}` : ''}
        `;
        segmentList.appendChild(segmentDiv);
    });
    
    // Fit map to bounds if segments exist
    if (segments.length > 0 && parkingOverlays.length > 0) {
        const group = L.featureGroup(parkingOverlays);
        map.fitBounds(group.getBounds().pad(0.1));
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
// Search address using Nominatim
async function searchAddress() {
    const address = document.getElementById('addressInput').value;
    if (!address) return;
    
    try {
        const response = await fetch(
            `https://nominatim.openstreetmap.org/search?` +
            `q=${encodeURIComponent(address + ', New York, NY')}&format=json&limit=1`
        );
        
        const results = await response.json();
        if (results.length > 0) {
            const { lat, lon } = results[0];
            map.setView([lat, lon], 17);
            setMarker(lat, lon);
            fetchParkingData(lat, lon);
        } else {
            alert('Address not found');
        }
    } catch (error) {
        console.error('Error searching address:', error);
    }
}

// Use current location
function useCurrentLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            position => {
                const { latitude, longitude } = position.coords;
                map.setView([latitude, longitude], 17);
                setMarker(latitude, longitude);
                fetchParkingData(latitude, longitude);
            },
            error => {
                console.error('Error getting location:', error);
                alert('Could not get your location');
            }
        );
    } else {
        alert('Geolocation is not supported by your browser');
    }
}

// Update parking display
function updateParkingDisplay() {
    if (currentLocation.lat && currentLocation.lng) {
        fetchParkingData(currentLocation.lat, currentLocation.lng);
    }
}

// Global variables for tracking
let isTracking = false;
let watchId = null;
let userMarker = null;

// Toggle location tracking
function toggleTracking() {
    const button = document.getElementById('trackingButton');
    
    if (!isTracking) {
        startTracking();
        button.textContent = 'Stop Following';
        button.style.background = '#f44336';
    } else {
        stopTracking();
        button.textContent = 'Follow My Location';
        button.style.background = '#4CAF50';
    }
    isTracking = !isTracking;
}

// Start continuous location tracking
function startTracking() {
    if (navigator.geolocation) {
        watchId = navigator.geolocation.watchPosition(
            position => {
                const { latitude, longitude } = position.coords;
                
                // Update user marker
                if (userMarker) {
                    userMarker.setLatLng([latitude, longitude]);
                } else {
                    userMarker = L.circleMarker([latitude, longitude], {
                        radius: 8,
                        fillColor: '#4285F4',
                        color: '#fff',
                        weight: 2,
                        opacity: 1,
                        fillOpacity: 0.8
                    }).addTo(map);
                }
                
                // Center map on user
                map.setView([latitude, longitude], map.getZoom());
                
                // Auto-fetch parking data if in NYC
                if (latitude > 40.4 && latitude < 41.0 && 
                    longitude > -74.3 && longitude < -73.7) {
                    fetchParkingData(latitude, longitude);
                }
            },
            error => {
                console.error('Tracking error:', error);
                alert('Could not track your location');
                stopTracking();
            },
            {
                enableHighAccuracy: true,
                maximumAge: 0,
                timeout: 5000
            }
        );
    }
}

// Stop tracking
function stopTracking() {
    if (watchId) {
        navigator.geolocation.clearWatch(watchId);
        watchId = null;
    }
}

// Initialize on load
window.onload = initMap;