#!/usr/bin/env python3
"""
Test script for NYC Parking Navigator Backend
Run this after starting the backend server
"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

# Test locations in Midtown Manhattan (where OpenCurb has data)
TEST_LOCATIONS = [
    {"name": "Times Square", "lat": 40.7580, "lon": -73.9855},
    {"name": "Grand Central", "lat": 40.7527, "lon": -73.9772},
    {"name": "Penn Station", "lat": 40.7506, "lon": -73.9935},
    {"name": "Herald Square", "lat": 40.7505, "lon": -73.9876},
    {"name": "Bryant Park", "lat": 40.7536, "lon": -73.9832}
]

# Test parking rules
TEST_RULES = [
    "NO PARKING 8AM-6PM MON THRU FRI",
    "NO STANDING ANYTIME",
    "2 HOUR PARKING 9AM-7PM EXCEPT SUNDAY",
    "NO PARKING 11AM-12:30PM TUE & FRI STREET CLEANING",
    "NO STOPPING 7AM-10AM 4PM-7PM EXCEPT SAT SUN",
    "METERED PARKING 9AM-6PM MON-SAT"
]

def test_health():
    """Test health endpoint"""
    print("\n1. Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ Health check passed")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_rule_parser():
    """Test parking rule parser"""
    print("\n2. Testing parking rule parser...")
    for rule in TEST_RULES:
        try:
            response = requests.get(
                f"{BASE_URL}/parking/rules/parse",
                params={"rule_text": rule}
            )
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Parsed: {rule}")
                print(f"   Type: {result.get('type')}")
                print(f"   Days: {result.get('days')}")
                print(f"   Time: {result.get('time_range')}")
            else:
                print(f"❌ Failed to parse: {rule}")
        except Exception as e:
            print(f"❌ Error parsing {rule}: {e}")
def test_parking_query():
    """Test parking query endpoint"""
    print("\n3. Testing parking query endpoint...")
    
    for location in TEST_LOCATIONS:
        print(f"\n   Testing {location['name']}...")
        
        # Test current time
        query_data = {
            "location": {
                "latitude": location['lat'],
                "longitude": location['lon']
            },
            "radius_meters": 200
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/parking/query",
                json=query_data
            )
            
            if response.status_code == 200:
                segments = response.json()
                print(f"   ✅ Found {len(segments)} parking segments")
                
                # Count by status
                status_counts = {}
                for seg in segments:
                    status = seg.get('current_status', 'UNKNOWN')
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                for status, count in status_counts.items():
                    print(f"      {status}: {count} segments")
            else:
                print(f"   ❌ Query failed: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

def test_time_based_query():
    """Test parking query at different times"""
    print("\n4. Testing time-based parking queries...")
    
    location = TEST_LOCATIONS[0]  # Times Square
    test_times = [
        ("Monday 10 AM", datetime.now().replace(hour=10, minute=0)),
        ("Monday 7 PM", datetime.now().replace(hour=19, minute=0)),
        ("Saturday 2 PM", datetime.now().replace(hour=14, minute=0)),
        ("Sunday 10 AM", datetime.now().replace(hour=10, minute=0))
    ]
    
    # Adjust to specific days
    for i, (name, dt) in enumerate(test_times):
        days_ahead = i % 7  # Spread across week
        dt = dt + timedelta(days=days_ahead)
        test_times[i] = (name, dt)
    for time_name, query_time in test_times:
        print(f"\n   Testing {time_name}...")
        
        query_data = {
            "location": {
                "latitude": location['lat'],
                "longitude": location['lon']
            },
            "radius_meters": 200,
            "query_time": query_time.isoformat()
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/parking/query",
                json=query_data
            )
            
            if response.status_code == 200:
                segments = response.json()
                
                # Count available vs restricted
                available = sum(1 for s in segments if s.get('status_color') == 'green')
                restricted = sum(1 for s in segments if s.get('status_color') == 'red')
                metered = sum(1 for s in segments if s.get('status_color') == 'blue')
                
                print(f"   ✅ Available: {available}, Restricted: {restricted}, Metered: {metered}")
            else:
                print(f"   ❌ Query failed: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

def test_location_endpoint():
    """Test simplified location endpoint"""
    print("\n5. Testing location endpoint...")
    
    location = TEST_LOCATIONS[0]
    try:
        response = requests.get(
            f"{BASE_URL}/parking/location/{location['lat']}/{location['lon']}",
            params={"radius": 150}
        )
        
        if response.status_code == 200:
            segments = response.json()
            print(f"✅ Location endpoint returned {len(segments)} segments")
        else:
            print(f"❌ Location endpoint failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    print("NYC Parking Navigator API Test Suite")
    print("=" * 50)
    print(f"Testing API at: {BASE_URL}")
    
    test_health()
    test_rule_parser()
    test_parking_query()
    test_time_based_query()
    test_location_endpoint()
    
    print("\n" + "=" * 50)
    print("Testing complete!")

if __name__ == "__main__":
    main()