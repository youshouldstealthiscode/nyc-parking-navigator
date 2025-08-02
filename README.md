# NYC Parking Navigator

An open-source real-time street parking navigation app for New York City that overlays parking regulations on a map while you drive.

## Features

- **Real-time parking overlay**: Green for available, red for restricted, blue for metered
- **Time-based rules**: Automatically updates based on current time and day
- **User tracking**: Follows your location with parking data overlay
- **Voice announcements**: "Parking available on your right for next 2 blocks"
- **Predictive parking**: Shows when spots will become available
- **Offline support**: Downloads regulation data for offline use

## Architecture

### Components

1. **Backend Service** (Python/FastAPI)
   - Processes NYC Open Data parking signs
   - Provides real-time parking availability API
   - Manages rule parsing and time calculations

2. **Data Pipeline** (Python/PostgreSQL)
   - Ingests data from NYC Open Data and OpenCurb
   - Parses complex parking rules
   - Maintains geospatial database

3. **Android App** (Kotlin/OpenStreetMap)
   - Real-time map with parking overlay
   - GPS tracking and navigation
   - Voice guidance and notifications

4. **Web Dashboard** (React/TypeScript)
   - Testing interface
   - Analytics and usage statistics
   - Admin panel for rule updates

## Data Sources

- **OpenCurb API**: Real-time parking regulations (Midtown Manhattan)
- **NYC Open Data**: Comprehensive parking signs database
- **NYC DOT**: Interactive parking regulations

## Getting Started

### Prerequisites
- Python 3.9+
- PostgreSQL with PostGIS
- Android Studio
- Node.js 16+

### Installation

1. Clone the repository
```bash
git clone https://github.com/yourusername/nyc-parking-navigator.git
cd nyc-parking-navigator
```

2. Set up the backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Set up the database
```bash
createdb nyc_parking
psql nyc_parking -c "CREATE EXTENSION postgis;"
python manage.py migrate
```

4. Run data pipeline
```bash
cd ../data-pipeline
python import_parking_data.py
```

5. Start the services
```bash
# Backend API
cd ../backend
uvicorn main:app --reload

# Web Dashboard
cd ../web-dashboard
npm install
npm start
```

6. Build Android app
```bash
cd ../android
./gradlew build
```

## License

This project is licensed under the MIT License - see LICENSE file for details.

## Contributing

We welcome contributions! Please see CONTRIBUTING.md for guidelines.

## Acknowledgments

- NYC Department of Transportation
- NYC Open Data
- OpenCurb project
- OpenStreetMap community