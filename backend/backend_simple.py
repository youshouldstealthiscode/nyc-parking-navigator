"""
NYC Parking Navigator - Lightweight Backend
Serves real NYC parking data for personal use
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
import re
from typing import List, Dict, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NYC Parking Navigator API", version="2.0.0")

# CORS for mobile app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
DATABASE_PATH = os.getenv("DATABASE_PATH", "parking_data.db")

# Models
class Location(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

class ParkingQuery(BaseModel):
    location: Location
    radius_meters: int = Field(default=300, ge=50, le=2000)

class ParkingSign(BaseModel):
    id: int
    street_name: str
    from_street: Optional[str]
    to_street: Optional[str]
    side: str
    description: str
    latitude: float
    longitude: float
    distance: float
    current_status: str
    status_color: str

class DestinationMonitor(BaseModel):
    destination: Location
    threshold_meters: int = Field(default=800, ge=100, le=5000)  # 0.5 miles default
    user_id: str

# Database connection
@contextmanager
def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# Helper functions
def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters using Haversine formula"""
    from math import radians, sin, cos, sqrt, atan2
    
    R = 6371000  # Earth radius in meters
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c

def parse_parking_rule(description: str, current_time: datetime) -> Tuple[str, str]:
    """Parse NYC parking sign description and return status"""
    if not description:
        return "UNKNOWN", "gray"
        
    desc_upper = description.upper()
    
    # Check for NO PARKING
    if "NO PARKING" in desc_upper:
        # Check time restrictions
        time_match = re.search(r'(\d{1,2})\s*(AM|PM)\s*-\s*(\d{1,2})\s*(AM|PM)', desc_upper)
        if time_match:
            # Parse times and check if currently restricted
            # Simplified - in production would parse full schedule
            return "NO_PARKING", "red"
        return "NO_PARKING", "red"
        
    # Check for METERED
    if "MUNI-METER" in desc_upper or "METERED" in desc_upper:
        return "METERED", "blue"
        
    # Check for street cleaning
    if "STREET CLEANING" in desc_upper:
        # Would parse schedule here
        return "STREET_CLEANING", "orange"
        
    # Free parking
    if "HOUR PARKING" in desc_upper and "NO PARKING" not in desc_upper:
        return "FREE_PARKING", "green"
        
    return "CHECK_SIGN", "yellow"

# Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM parking_signs")
            count = cursor.fetchone()[0]
            
        return {
            "status": "healthy",
            "database": "connected",
            "total_signs": count,
            "version": "2.0.0"
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.post("/api/v1/parking/query")
async def query_parking(query: ParkingQuery) -> List[ParkingSign]:
    """Get parking signs near a location"""
    
    # Convert radius to approximate lat/lon degrees
    # 1 degree latitude ≈ 111,000 meters
    lat_radius = query.radius_meters / 111000
    lon_radius = query.radius_meters / (111000 * cos(radians(query.location.latitude)))
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Query signs within bounding box
        cursor.execute("""
            SELECT 
                id, main_st, from_st, to_st, side_of_street, 
                sign_description, latitude, longitude
            FROM parking_signs
            WHERE latitude BETWEEN ? AND ?
            AND longitude BETWEEN ? AND ?
            AND latitude IS NOT NULL
            AND longitude IS NOT NULL
        """, (
            query.location.latitude - lat_radius,
            query.location.latitude + lat_radius,
            query.location.longitude - lon_radius,
            query.location.longitude + lon_radius
        ))
        
        results = []
        current_time = datetime.now()
        
        for row in cursor.fetchall():
            # Calculate actual distance
            distance = calculate_distance(
                query.location.latitude,
                query.location.longitude,
                row['latitude'],
                row['longitude']
            )
            
            # Only include within actual radius
            if distance <= query.radius_meters:
                status, color = parse_parking_rule(row['sign_description'], current_time)
                
                results.append(ParkingSign(
                    id=row['id'],
                    street_name=row['main_st'] or "Unknown Street",
                    from_street=row['from_st'],
                    to_street=row['to_st'],
                    side=row['side_of_street'] or "Unknown",
                    description=row['sign_description'] or "No description",
                    latitude=row['latitude'],
                    longitude=row['longitude'],
                    distance=round(distance),
                    current_status=status,
                    status_color=color
                ))
        
        # Sort by distance
        results.sort(key=lambda x: x.distance)
        
        logger.info(f"Found {len(results)} parking signs near {query.location.latitude}, {query.location.longitude}")
        
        return results

@app.get("/api/v1/parking/streets")
async def get_streets_list(borough: str = Query(None)) -> List[str]:
    """Get list of all streets for autocomplete"""
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        if borough:
            cursor.execute("""
                SELECT DISTINCT main_st 
                FROM parking_signs 
                WHERE boro = ? AND main_st IS NOT NULL
                ORDER BY main_st
            """, (borough.upper(),))
        else:
            cursor.execute("""
                SELECT DISTINCT main_st 
                FROM parking_signs 
                WHERE main_st IS NOT NULL
                ORDER BY main_st
            """)
            
        return [row[0] for row in cursor.fetchall()]

@app.post("/api/v1/destination/monitor")
async def monitor_destination(monitor: DestinationMonitor) -> Dict:
    """Set up destination monitoring for auto-launch"""
    
    # In a real implementation, this would:
    # 1. Store the destination in Redis/memory
    # 2. Set up a geofence on the mobile device
    # 3. Return a monitor ID
    
    monitor_id = f"mon_{monitor.user_id}_{int(datetime.now().timestamp())}"
    
    # For demo, just return the setup
    return {
        "monitor_id": monitor_id,
        "destination": {
            "lat": monitor.destination.latitude,
            "lon": monitor.destination.longitude
        },
        "threshold_meters": monitor.threshold_meters,
        "status": "active",
        "eta_minutes": 15  # Would calculate from current location
    }

@app.get("/api/v1/stats")
async def get_stats() -> Dict:
    """Get database statistics"""
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Total signs
        cursor.execute("SELECT COUNT(*) FROM parking_signs")
        total = cursor.fetchone()[0]
        
        # By borough
        cursor.execute("""
            SELECT boro, COUNT(*) 
            FROM parking_signs 
            GROUP BY boro
        """)
        by_borough = dict(cursor.fetchall())
        
        # Coverage area
        cursor.execute("""
            SELECT 
                MIN(latitude) as south, 
                MAX(latitude) as north,
                MIN(longitude) as west,
                MAX(longitude) as east
            FROM parking_signs
            WHERE latitude IS NOT NULL
        """)
        bounds = cursor.fetchone()
        
        return {
            "total_signs": total,
            "by_borough": by_borough,
            "coverage_area": {
                "south": bounds[0],
                "north": bounds[1],
                "west": bounds[2],
                "east": bounds[3]
            },
            "last_updated": datetime.now().isoformat()
        }

# Run with: uvicorn backend_simple:app --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    
    # Check if database exists
    if not os.path.exists(DATABASE_PATH):
        logger.error(f"Database not found at {DATABASE_PATH}")
        logger.info("Run 'python scripts/download_nyc_data.py' first to download NYC parking data")
        exit(1)
        
    uvicorn.run(app, host="0.0.0.0", port=8000)