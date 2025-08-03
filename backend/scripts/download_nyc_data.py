#!/usr/bin/env python3
"""
Download and process NYC parking sign data from NYC Open Data
Creates a SQLite database with all parking regulations
"""

import requests
import sqlite3
import json
from datetime import datetime
import os
import sys

# NYC Open Data API endpoint for parking signs
NYC_PARKING_SIGNS_API = "https://data.cityofnewyork.us/resource/8br5-fqav.json"
DATABASE_PATH = "../parking_data.db"

def download_parking_data():
    """Download all parking sign data from NYC Open Data"""
    print("🚀 Downloading NYC parking sign data...")
    print("This will take a few minutes for 1.2M+ records...")
    
    all_records = []
    offset = 0
    limit = 50000  # API limit per request
    
    while True:
        url = f"{NYC_PARKING_SIGNS_API}?$limit={limit}&$offset={offset}"
        print(f"  Downloading records {offset} to {offset + limit}...")
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if not data:
                break
                
            all_records.extend(data)
            offset += limit
            
            # Progress indicator
            print(f"  ✓ Downloaded {len(all_records)} records so far...")
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error downloading data: {e}")
            return None
            
    print(f"✅ Downloaded {len(all_records)} total parking signs!")
    return all_records

def create_database(records):
    """Create SQLite database with parking sign data"""
    print("\n📊 Creating database...")
    
    # Remove old database if exists
    if os.path.exists(DATABASE_PATH):
        os.remove(DATABASE_PATH)
        
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Create table with all fields from NYC data
    cursor.execute('''
        CREATE TABLE parking_signs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            objectid TEXT,
            boro TEXT,
            order_no TEXT,
            p_sign_seq TEXT,
            main_st TEXT,
            from_st TEXT,
            to_st TEXT,
            side_of_street TEXT,
            sign_description TEXT,
            arrow_direction TEXT,
            latitude REAL,
            longitude REAL,
            x_coord REAL,
            y_coord REAL,
            point_geom TEXT,
            last_painted TEXT,
            created_date TEXT,
            last_edited_date TEXT
        )
    ''')
    
    # Insert all records
    print("  Inserting records...")
    for i, record in enumerate(records):
        # Extract coordinates from point geometry
        lat, lon = None, None
        if 'point' in record and 'coordinates' in record['point']:
            lon, lat = record['point']['coordinates']
        
        cursor.execute('''
            INSERT INTO parking_signs (
                objectid, boro, order_no, p_sign_seq,
                main_st, from_st, to_st, side_of_street,
                sign_description, arrow_direction,
                latitude, longitude, x_coord, y_coord,
                point_geom, last_painted, created_date, last_edited_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record.get('objectid'),
            record.get('boro'),
            record.get('order_no'),
            record.get('p_sign_seq'),
            record.get('main_st'),
            record.get('from_st'),
            record.get('to_st'),
            record.get('sos'),  # side of street
            record.get('signdesc1'),  # sign description
            record.get('arrow'),
            lat,
            lon,
            record.get('point', {}).get('coordinates', [None, None])[0],
            record.get('point', {}).get('coordinates', [None, None])[1],
            json.dumps(record.get('point', {})),
            record.get('lastpainteddate'),
            record.get('created_date'),
            record.get('last_edited_date')
        ))
        
        if i % 10000 == 0:
            print(f"  ✓ Inserted {i} records...")
            
    # Create indexes for fast queries
    print("  Creating indexes...")
    cursor.execute('CREATE INDEX idx_location ON parking_signs(latitude, longitude)')
    cursor.execute('CREATE INDEX idx_main_street ON parking_signs(main_st)')
    cursor.execute('CREATE INDEX idx_boro ON parking_signs(boro)')
    cursor.execute('CREATE INDEX idx_description ON parking_signs(sign_description)')
    
    conn.commit()
    
    # Get some stats
    cursor.execute('SELECT COUNT(*) FROM parking_signs')
    total = cursor.fetchone()[0]
    
    cursor.execute('SELECT boro, COUNT(*) FROM parking_signs GROUP BY boro')
    borough_counts = cursor.fetchall()
    
    conn.close()
    
    print(f"\n✅ Database created successfully!")
    print(f"📈 Statistics:")
    print(f"  Total signs: {total:,}")
    for boro, count in borough_counts:
        print(f"  {boro}: {count:,} signs")
    
    # File size
    size_mb = os.path.getsize(DATABASE_PATH) / (1024 * 1024)
    print(f"  Database size: {size_mb:.1f} MB")

def test_database():
    """Test the database with some sample queries"""
    print("\n🧪 Testing database...")
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Test query: Find parking signs near Times Square
    lat, lon = 40.7580, -73.9855
    radius = 0.005  # About 500 meters
    
    cursor.execute('''
        SELECT main_st, from_st, to_st, side_of_street, sign_description
        FROM parking_signs
        WHERE latitude BETWEEN ? AND ?
        AND longitude BETWEEN ? AND ?
        LIMIT 5
    ''', (lat - radius, lat + radius, lon - radius, lon + radius))
    
    results = cursor.fetchall()
    print(f"\n  Sample signs near Times Square:")
    for row in results:
        print(f"  • {row[0]} ({row[1]} to {row[2]}), {row[3]} side: {row[4]}")
        
    conn.close()

if __name__ == "__main__":
    print("="*60)
    print("NYC Parking Data Downloader")
    print("="*60)
    
    # Download data
    records = download_parking_data()
    
    if records:
        # Create database
        create_database(records)
        
        # Test it
        test_database()
        
        print("\n🎉 All done! Database is ready at:", DATABASE_PATH)
        print("\nTo update data weekly, run:")
        print("  python3 download_nyc_data.py")
    else:
        print("\n❌ Failed to download data. Please try again.")
        sys.exit(1)