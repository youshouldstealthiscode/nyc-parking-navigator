# NYC Parking Navigator Backend Service

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, time
import httpx
from geopy.distance import geodesic
import json
import re

app = FastAPI(title="NYC Parking Navigator API", version="1.0.0")

# Enable CORS for web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models
class Location(BaseModel):
    latitude: float
    longitude: float

class ParkingSegment(BaseModel):
    segment_id: str
    coordinates: List[List[float]]
    street_name: str
    side: str
    regulations: List[Dict]
    current_status: str
    status_color: str
    next_change: Optional[datetime]

class ParkingQuery(BaseModel):
    location: Location
    radius_meters: int = 500
    query_time: Optional[datetime] = None

# Parking rule parser
class ParkingRuleParser:
    def __init__(self):
        self.days_map = {
            'MON': 0, 'TUE': 1, 'WED': 2, 'THU': 3, 
            'FRI': 4, 'SAT': 5, 'SUN': 6,
            'MONDAY': 0, 'TUESDAY': 1, 'WEDNESDAY': 2, 
            'THURSDAY': 3, 'FRIDAY': 4, 'SATURDAY': 5, 'SUNDAY': 6
        }
        
    def parse_time_range(self, time_str: str) -> tuple:
        """Parse time range like '8AM-6PM' """
        pattern = r'(\d{1,2}):?(\d{2})?\s*(AM|PM)'
        matches = re.findall(pattern, time_str.upper())
        if len(matches) >= 2:
            start_hour = int(matches[0][0])
            start_min = int(matches[0][1]) if matches[0][1] else 0
            if matches[0][2] == 'PM' and start_hour != 12:
                start_hour += 12
            elif matches[0][2] == 'AM' and start_hour == 12:
                start_hour = 0
                
            end_hour = int(matches[1][0])
            end_min = int(matches[1][1]) if matches[1][1] else 0
            if matches[1][2] == 'PM' and end_hour != 12:
                end_hour += 12
            elif matches[1][2] == 'AM' and end_hour == 12:
                end_hour = 0
                
            return (time(start_hour, start_min), time(end_hour, end_min))
        return None    
    def parse_days(self, day_str: str) -> List[int]:
        """Parse day strings like 'MON THRU FRI' or 'TUE & FRI'"""
        days = []
        day_str = day_str.upper()
        
        if 'THRU' in day_str or 'THROUGH' in day_str:
            parts = re.split(r'THRU|THROUGH', day_str)
            if len(parts) == 2:
                start_day = parts[0].strip()
                end_day = parts[1].strip()
                if start_day in self.days_map and end_day in self.days_map:
                    start_idx = self.days_map[start_day]
                    end_idx = self.days_map[end_day]
                    days = list(range(start_idx, end_idx + 1))
        elif '&' in day_str:
            day_parts = day_str.split('&')
            for day in day_parts:
                day = day.strip()
                if day in self.days_map:
                    days.append(self.days_map[day])
        else:
            # Single day
            day_str = day_str.strip()
            if day_str in self.days_map:
                days.append(self.days_map[day_str])
                
        return days
    
    def parse_rule(self, rule_text: str) -> Dict:
        """Parse a parking rule text into structured format"""
        rule_text = rule_text.upper()
        parsed = {
            'original_text': rule_text,
            'type': 'UNKNOWN',
            'days': [],
            'time_range': None,
            'restrictions': []
        }
        
        # Determine rule type
        if 'NO PARKING' in rule_text:
            parsed['type'] = 'NO_PARKING'
        elif 'NO STANDING' in rule_text:
            parsed['type'] = 'NO_STANDING'
        elif 'NO STOPPING' in rule_text:
            parsed['type'] = 'NO_STOPPING'
        elif 'HOUR PARKING' in rule_text:
            parsed['type'] = 'METERED'
        elif 'STREET CLEANING' in rule_text:
            parsed['type'] = 'STREET_CLEANING'
            
        # Extract time range
        time_pattern = r'(\d{1,2}:?\d{0,2}\s*[AP]M)\s*-\s*(\d{1,2}:?\d{0,2}\s*[AP]M)'
        time_match = re.search(time_pattern, rule_text)
        if time_match:
            parsed['time_range'] = self.parse_time_range(time_match.group())
            
        # Extract days
        day_patterns = [
            r'(MON|TUE|WED|THU|FRI|SAT|SUN)(?:\s*(?:THRU|THROUGH|&)\s*(MON|TUE|WED|THU|FRI|SAT|SUN))*',
            r'(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY)'
        ]
        for pattern in day_patterns:
            day_match = re.search(pattern, rule_text)
            if day_match:
                parsed['days'] = self.parse_days(day_match.group())
                break
                
        return parsed
# Initialize parser
parser = ParkingRuleParser()

# OpenCurb API integration
class OpenCurbClient:
    def __init__(self):
        self.base_url = "https://api.opencurb.nyc/v1"
        
    async def get_parking_data(self, lat: float, lon: float, radius: int) -> List[Dict]:
        """Fetch parking data from OpenCurb API"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/regulations",
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "radius": radius
                    }
                )
                if response.status_code == 200:
                    return response.json()
                return []
            except Exception as e:
                print(f"Error fetching OpenCurb data: {e}")
                return []

opencurb_client = OpenCurbClient()

# Helper functions
def is_parking_allowed(regulations: List[Dict], check_time: datetime) -> tuple:
    """Check if parking is allowed at given time"""
    current_day = check_time.weekday()
    current_time = check_time.time()
    
    # Start with assumption that parking is allowed
    allowed = True
    restriction_type = None
    
    for rule in regulations:
        parsed = parser.parse_rule(rule.get('description', ''))
        
        # Check if rule applies to current day
        if current_day not in parsed['days'] and parsed['days']:
            continue
            
        # Check if rule applies to current time
        if parsed['time_range']:
            start_time, end_time = parsed['time_range']
            if start_time <= current_time <= end_time:
                # Rule is active
                if parsed['type'] in ['NO_PARKING', 'NO_STANDING', 'NO_STOPPING']:
                    allowed = False
                    restriction_type = parsed['type']
                elif parsed['type'] == 'METERED':
                    restriction_type = 'METERED'
                    
    return allowed, restriction_type
# API Endpoints
@app.get("/")
async def root():
    return {"message": "NYC Parking Navigator API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

@app.post("/parking/query", response_model=List[ParkingSegment])
async def query_parking(query: ParkingQuery):
    """Query parking availability for a specific location and time"""
    
    # Use current time if not specified
    query_time = query.query_time or datetime.now()
    
    # Fetch data from OpenCurb
    parking_data = await opencurb_client.get_parking_data(
        query.location.latitude,
        query.location.longitude,
        query.radius_meters
    )
    
    # Process each parking segment
    segments = []
    for feature in parking_data:
        if feature.get('type') == 'Feature':
            geometry = feature.get('geometry', {})
            properties = feature.get('properties', {})
            
            # Check parking availability
            regulations = properties.get('regulations', [])
            allowed, restriction_type = is_parking_allowed(regulations, query_time)
            
            # Determine status color
            if not allowed:
                status_color = 'red'
                current_status = restriction_type or 'NO_PARKING'
            elif restriction_type == 'METERED':
                status_color = 'blue'
                current_status = 'METERED'
            else:
                status_color = 'green'
                current_status = 'AVAILABLE'
                
            segment = ParkingSegment(
                segment_id=properties.get('id', ''),
                coordinates=geometry.get('coordinates', []),
                street_name=properties.get('street_name', ''),
                side=properties.get('side', ''),
                regulations=regulations,
                current_status=current_status,
                status_color=status_color,
                next_change=None  # TODO: Calculate next status change
            )
            segments.append(segment)
    return segments

@app.get("/parking/location/{lat}/{lon}")
async def get_parking_at_location(
    lat: float, 
    lon: float, 
    radius: int = Query(default=200, ge=50, le=1000)
):
    """Get parking info for specific coordinates"""
    query = ParkingQuery(
        location=Location(latitude=lat, longitude=lon),
        radius_meters=radius
    )
    return await query_parking(query)

@app.get("/parking/rules/parse")
async def parse_parking_rule(rule_text: str):
    """Parse a parking rule text for testing"""
    return parser.parse_rule(rule_text)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)