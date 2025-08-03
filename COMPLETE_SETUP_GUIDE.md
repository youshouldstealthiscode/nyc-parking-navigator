# NYC Parking Navigator - Complete Setup Guide

## 🚀 Quick Start (10 minutes to fully working app!)

This guide will get you a fully functional parking app with real NYC data for personal use (up to 10 users).

## 📊 Real NYC Parking Data

We use **NYC Open Data** which provides:
- **1.2 million+ parking signs** across all 5 boroughs
- Updated weekly by NYC DOT
- Free, no API key required
- Complete parking regulations

## 🗺️ F/LOSS Map Solution (OpenStreetMap)

Instead of Google Maps, we use:
- **OpenStreetMap** for map data (free, no limits)
- **Mapbox GL** or **Leaflet** for rendering
- No API keys required for basic use
- Works offline after initial download

## 🖥️ Simple Backend Setup

### Option 1: One-Click Cloud Deploy (Recommended)

Deploy to free tier of Railway, Render, or Fly.io:

```bash
# Clone the repo
git clone https://github.com/youshouldstealthiscode/nyc-parking-navigator
cd nyc-parking-navigator

# Deploy to Railway (free tier)
railway login
railway up

# Your API will be at: https://your-app.railway.app
```

### Option 2: Raspberry Pi / Home Server

```bash
# On your Raspberry Pi or home server
cd nyc-parking-navigator/backend

# Install dependencies
pip3 install -r requirements.txt

# Download NYC parking data (one-time, ~200MB)
python3 scripts/download_nyc_data.py

# Start the server
python3 main.py --host 0.0.0.0 --port 8000

# Access at: http://your-pi-ip:8000
```

### Option 3: Lightweight VPS (DigitalOcean, Linode)

$5/month VPS is more than enough for 10 users:

```bash
# SSH into your VPS
ssh root@your-vps-ip

# Quick install script
curl -sSL https://raw.githubusercontent.com/youshouldstealthiscode/nyc-parking-navigator/master/install.sh | bash

# Server starts automatically
# Access at: http://your-vps-ip
```

## 📱 Smart Auto-Launch Feature

The app includes a background service that:

1. **Monitors your destination** (from any navigation app)
2. **Auto-launches** when you're within your threshold (default: 0.5 miles)
3. **Voice announces**: "Approaching destination in 2 minutes. Searching for parking."
4. **Switches to parking mode** automatically

### How It Works:
- Reads destination from Android's shared navigation intent
- Uses geofencing for efficient battery usage
- Works with Google Maps, Waze, Apple Maps, etc.
- No fumbling with phone while driving!

## 🔧 Configuration

### 1. Set Your Backend URL

In the app settings, change from demo to your server:
- Demo: `http://10.0.2.2:8000`
- Your server: `http://your-server-ip:8000`

### 2. Download Offline Maps (Optional)

For offline use:
1. Open app settings
2. Tap "Download Offline Maps"
3. Select your area (Manhattan, Brooklyn, etc.)
4. Maps work without internet!

### 3. Auto-Launch Settings

Configure in app:
- **Trigger Distance**: 0.1 - 2 miles from destination
- **Voice Alerts**: On/Off
- **Auto-Open**: On/Off
- **Integration**: Works with any navigation app

## 📊 Database Details

### NYC Parking Data Structure

```sql
-- Parking signs table (1.2M+ records)
CREATE TABLE parking_signs (
    id INTEGER PRIMARY KEY,
    borough TEXT,
    order_no TEXT,
    main_street TEXT,
    from_street TEXT,
    to_street TEXT,
    side_of_street TEXT,
    sign_description TEXT,
    latitude REAL,
    longitude REAL,
    geom TEXT
);

-- Indexed for fast queries
CREATE INDEX idx_location ON parking_signs(latitude, longitude);
CREATE INDEX idx_street ON parking_signs(main_street);
```

### Data Freshness
- Updated weekly from NYC Open Data
- Auto-refresh script included
- ~200MB SQLite database
- Covers all 5 boroughs

## 🚦 Complete Backend Code

Here's the simplified backend that handles everything: