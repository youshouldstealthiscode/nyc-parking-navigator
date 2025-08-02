#!/usr/bin/env python3
"""
NYC Parking Navigator - Interactive Demo
Shows key features of the parking navigation system
"""

import requests
import json
from datetime import datetime, timedelta
import time

BASE_URL = "http://localhost:8000"

def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f" {text}")
    print("=" * 60)

def demo_rule_parsing():
    """Demonstrate parking rule parsing"""
    print_header("FEATURE 1: Smart Parking Rule Parser")
    
    rules = [
        "NO PARKING 8AM-6PM MON THRU FRI",
        "2 HOUR PARKING 9AM-7PM EXCEPT SUNDAY",
        "NO PARKING 11AM-12:30PM TUE & FRI STREET CLEANING"
    ]
    
    print("\nOur parser understands complex NYC parking signs:")
    
    for rule in rules:
        response = requests.get(
            f"{BASE_URL}/parking/rules/parse",
            params={"rule_text": rule}
        )
        
        if response.status_code == 200:
            parsed = response.json()
            print(f"\n📋 Sign: '{rule}'")
            print(f"   ↳ Type: {parsed.get('type')}")
            print(f"   ↳ Days: {', '.join([['MON','TUE','WED','THU','FRI','SAT','SUN'][d] for d in parsed.get('days', [])])}")
            if parsed.get('time_range'):
                print(f"   ↳ Hours: {parsed.get('time_range')}")
        
        time.sleep(0.5)

def demo_real_time_query():
    """Demonstrate real-time parking queries"""
    print_header("FEATURE 2: Real-Time Parking Availability")
    
    print("\n🗺️  Checking parking around Times Square...")
    
    # Current time query
    response = requests.post(
        f"{BASE_URL}/parking/query",
        json={
            "location": {"latitude": 40.7580, "longitude": -73.9855},
            "radius_meters": 200
        }
    )
    
    if response.status_code == 200:
        segments = response.json()
        
        # Count statuses
        status_counts = {}
        for seg in segments:
            color = seg.get('status_color', 'gray')
            status_counts[color] = status_counts.get(color, 0) + 1
        
        print(f"\nFound {len(segments)} parking segments:")
        print(f"   🟢 Available: {status_counts.get('green', 0)} segments")
        print(f"   🔴 Restricted: {status_counts.get('red', 0)} segments") 
        print(f"   🔵 Metered: {status_counts.get('blue', 0)} segments")
        
        # Show a few examples
        if segments:
            print("\nExample segments:")
            for seg in segments[:3]:
                icon = {"green": "✅", "red": "🚫", "blue": "💰"}.get(seg['status_color'], "❓")
                print(f"   {icon} {seg['street_name']} ({seg['side']} side) - {seg['current_status']}")
def demo_time_based_predictions():
    """Demonstrate time-based parking predictions"""
    print_header("FEATURE 3: Time-Based Parking Predictions")
    
    print("\n⏰ Checking how parking changes throughout the day...")
    
    location = {"latitude": 40.7527, "longitude": -73.9772}  # Grand Central
    
    # Check different times
    now = datetime.now()
    times_to_check = [
        ("Right now", now),
        ("In 2 hours", now + timedelta(hours=2)),
        ("Tonight at 8 PM", now.replace(hour=20, minute=0)),
        ("Tomorrow morning", (now + timedelta(days=1)).replace(hour=9, minute=0))
    ]
    
    for label, check_time in times_to_check:
        response = requests.post(
            f"{BASE_URL}/parking/query",
            json={
                "location": location,
                "radius_meters": 150,
                "query_time": check_time.isoformat()
            }
        )
        
        if response.status_code == 200:
            segments = response.json()
            available = sum(1 for s in segments if s.get('status_color') == 'green')
            total = len(segments)
            
            print(f"\n   {label} ({check_time.strftime('%a %I:%M %p')})")
            print(f"   ↳ {available}/{total} segments available ({int(available/total*100) if total else 0}%)")
        
        time.sleep(0.5)

def demo_voice_announcements():
    """Demonstrate voice announcement feature"""
    print_header("FEATURE 4: Voice Announcements (Android App)")
    
    print("\n🔊 In the Android app, you would hear:")
    print('\n   "Parking available on 42nd Street, east side"')
    print('   "No parking zone ahead for next 2 blocks"')
    print('   "Metered parking on your right"')
    
    print("\n📱 The app announces parking changes as you drive!")

def demo_coverage_area():
    """Show current coverage area"""
    print_header("CURRENT COVERAGE")
    
    print("\n📍 OpenCurb data currently covers:")
    print("   • Midtown Manhattan (30th St to 59th St)")
    print("   • Both East and West sides")
    
    print("\n🚀 NYC Open Data provides city-wide coverage:")
    print("   • All 5 boroughs")
    print("   • Over 1 million parking signs")
    print("   • Updated daily")

def main():
    print("\n🚗 NYC PARKING NAVIGATOR - LIVE DEMO 🚗")
    print("Real-time street parking for New York City")
    
    try:
        # Check if backend is running
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code != 200:
            raise Exception("Backend not responding")
    except:
        print("\n⚠️  ERROR: Backend server is not running!")
        print("Please run: cd backend && uvicorn main:app --reload")
        return
    
    demo_rule_parsing()
    time.sleep(1)
    
    demo_real_time_query()
    time.sleep(1)
    
    demo_time_based_predictions()
    time.sleep(1)
    
    demo_voice_announcements()
    time.sleep(1)
    
    demo_coverage_area()
    
    print_header("READY TO USE!")
    print("\n✅ Backend API: http://localhost:8000/docs")
    print("✅ Web Dashboard: http://localhost:8080")
    print("✅ Android app: Ready to build in Android Studio")
    
    print("\n🎯 Next steps:")
    print("   1. Open the web dashboard to visualize parking")
    print("   2. Click anywhere on the map to check parking")
    print("   3. Try different times to see how parking changes")
    print("   4. Build the Android app for real-time navigation")

if __name__ == "__main__":
    main()