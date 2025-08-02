#!/usr/bin/env python3
"""
NYC Parking Data Pipeline
Fetches and processes parking regulation data from NYC Open Data
"""

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
import requests
import json
from datetime import datetime
import psycopg2
from sqlalchemy import create_engine
import os
from typing import Dict, List, Tuple

class NYCParkingDataPipeline:
    def __init__(self, db_connection_string: str = None):
        self.db_connection = db_connection_string or "postgresql://localhost/nyc_parking"
        self.engine = create_engine(self.db_connection)
        
        # NYC Open Data endpoints
        self.endpoints = {
            'parking_signs': 'https://data.cityofnewyork.us/resource/xswq-wnv9.json',
            'parking_meters': 'https://data.cityofnewyork.us/resource/693u-f9ye.json',
            'opencurb': 'https://api.opencurb.nyc/v1/regulations'
        }
        
    def fetch_parking_signs(self, limit: int = None) -> pd.DataFrame:
        """Fetch parking signs data from NYC Open Data"""
        print("Fetching parking signs data...")
        
        params = {
            '$limit': limit or 50000,
            '$order': 'objectid'
        }
        
        try:
            response = requests.get(self.endpoints['parking_signs'], params=params)
            response.raise_for_status()
            data = response.json()
            
            df = pd.DataFrame(data)
            print(f"Fetched {len(df)} parking sign records")
            return df
            
        except Exception as e:
            print(f"Error fetching parking signs: {e}")
            return pd.DataFrame()
    def process_parking_signs(self, df: pd.DataFrame) -> gpd.GeoDataFrame:
        """Process parking signs data into GeoDataFrame"""
        print("Processing parking signs...")
        
        # Extract coordinates
        df['longitude'] = pd.to_numeric(df.get('longitude', 0), errors='coerce')
        df['latitude'] = pd.to_numeric(df.get('latitude', 0), errors='coerce')
        
        # Remove invalid coordinates
        df = df[(df['longitude'] != 0) & (df['latitude'] != 0)]
        df = df.dropna(subset=['longitude', 'latitude'])
        
        # Create geometry
        geometry = [Point(xy) for xy in zip(df.longitude, df.latitude)]
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs='EPSG:4326')
        
        # Parse sign descriptions
        gdf['parsed_rules'] = gdf['signdescription'].apply(self.parse_sign_description)
        
        print(f"Processed {len(gdf)} valid parking signs")
        return gdf
        
    def parse_sign_description(self, description: str) -> Dict:
        """Parse sign description into structured format"""
        if pd.isna(description):
            return {}
            
        # This uses the same parsing logic as the API
        from main import ParkingRuleParser
        parser = ParkingRuleParser()
        return parser.parse_rule(description)
        
    def fetch_opencurb_data(self, bounds: Tuple[float, float, float, float]) -> List[Dict]:
        """Fetch OpenCurb data for given bounds"""
        print("Fetching OpenCurb data...")
        
        # OpenCurb currently only covers Midtown Manhattan
        params = {
            'min_lat': bounds[0],
            'min_lon': bounds[1],
            'max_lat': bounds[2],
            'max_lon': bounds[3]
        }
        
        try:
            response = requests.get(self.endpoints['opencurb'], params=params)
            response.raise_for_status()
            data = response.json()
            
            print(f"Fetched {len(data.get('features', []))} OpenCurb segments")
            return data.get('features', [])
            
        except Exception as e:
            print(f"Error fetching OpenCurb data: {e}")
            return []
    def create_database_schema(self):
        """Create database tables for parking data"""
        print("Creating database schema...")
        
        create_tables_sql = """
        -- Enable PostGIS extension
        CREATE EXTENSION IF NOT EXISTS postgis;
        
        -- Parking signs table
        CREATE TABLE IF NOT EXISTS parking_signs (
            id SERIAL PRIMARY KEY,
            sign_id VARCHAR(50) UNIQUE,
            description TEXT,
            street_name VARCHAR(255),
            longitude DOUBLE PRECISION,
            latitude DOUBLE PRECISION,
            geometry GEOMETRY(Point, 4326),
            parsed_rules JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Parking segments table (from OpenCurb)
        CREATE TABLE IF NOT EXISTS parking_segments (
            id SERIAL PRIMARY KEY,
            segment_id VARCHAR(100) UNIQUE,
            street_name VARCHAR(255),
            side VARCHAR(20),
            geometry GEOMETRY(LineString, 4326),
            regulations JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Create spatial indices
        CREATE INDEX IF NOT EXISTS idx_parking_signs_geometry 
            ON parking_signs USING GIST (geometry);
        CREATE INDEX IF NOT EXISTS idx_parking_segments_geometry 
            ON parking_segments USING GIST (geometry);
        """
        
        try:
            with psycopg2.connect(self.db_connection) as conn:
                with conn.cursor() as cur:
                    cur.execute(create_tables_sql)
                conn.commit()
            print("Database schema created successfully")
        except Exception as e:
            print(f"Error creating database schema: {e}")
    def load_to_database(self, gdf: gpd.GeoDataFrame, table_name: str):
        """Load GeoDataFrame to PostGIS database"""
        print(f"Loading data to {table_name}...")
        
        try:
            gdf.to_postgis(
                table_name, 
                self.engine, 
                if_exists='append',
                index=False
            )
            print(f"Loaded {len(gdf)} records to {table_name}")
        except Exception as e:
            print(f"Error loading data to database: {e}")
            
    def run_pipeline(self):
        """Run the complete data pipeline"""
        print("Starting NYC Parking Data Pipeline...")
        print("=" * 50)
        
        # Create database schema
        self.create_database_schema()
        
        # Fetch and process parking signs
        signs_df = self.fetch_parking_signs(limit=10000)  # Start with 10k for testing
        if not signs_df.empty:
            signs_gdf = self.process_parking_signs(signs_df)
            self.load_to_database(signs_gdf, 'parking_signs')
            
        # Fetch OpenCurb data for Midtown Manhattan
        midtown_bounds = (40.745, -74.000, 40.770, -73.970)  # Rough bounds
        opencurb_data = self.fetch_opencurb_data(midtown_bounds)
        
        if opencurb_data:
            # Process OpenCurb segments
            segments = []
            for feature in opencurb_data:
                if feature.get('geometry', {}).get('type') == 'LineString':
                    segments.append({
                        'segment_id': feature.get('properties', {}).get('id'),
                        'street_name': feature.get('properties', {}).get('street_name'),
                        'side': feature.get('properties', {}).get('side'),
                        'geometry': LineString(feature['geometry']['coordinates']),
                        'regulations': json.dumps(feature.get('properties', {}).get('regulations', []))
                    })
                    
            if segments:
                segments_gdf = gpd.GeoDataFrame(segments, crs='EPSG:4326')
                self.load_to_database(segments_gdf, 'parking_segments')
                
        print("\nPipeline completed!")
        print("=" * 50)

if __name__ == "__main__":
    pipeline = NYCParkingDataPipeline()
    pipeline.run_pipeline()