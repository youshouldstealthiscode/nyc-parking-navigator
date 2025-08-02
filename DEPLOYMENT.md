# NYC Parking Navigator - Deployment Guide

## Quick Start

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the API server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`
API documentation at `http://localhost:8000/docs`

### 2. Database Setup (Optional - for full data)

```bash
# Install PostgreSQL if not already installed
brew install postgresql postgis  # macOS
# or
sudo apt-get install postgresql postgresql-contrib postgis  # Ubuntu

# Create database
createdb nyc_parking
psql nyc_parking -c "CREATE EXTENSION postgis;"

# Run data pipeline
cd ../data-pipeline
python import_parking_data.py
```
### 3. Web Dashboard

```bash
cd web-dashboard

# For development, you can use Python's built-in server
python3 -m http.server 8080

# Or use Node.js
npx http-server -p 8080
```

Open `http://localhost:8080` in your browser.

### 4. Android App

1. Open the `android` folder in Android Studio
2. Update `MainActivity.kt` with your server IP:
   ```kotlin
   .baseUrl("http://YOUR_COMPUTER_IP:8000/")
   ```
3. Add Google Maps API key to `local.properties`:
   ```
   MAPS_API_KEY=your_google_maps_api_key
   ```
4. Run on device or emulator

## Testing the System

### 1. Test Backend API

```bash
# Health check
curl http://localhost:8000/health

# Test parking query (Times Square)
curl -X POST http://localhost:8000/parking/query \
  -H "Content-Type: application/json" \
  -d '{
    "location": {"latitude": 40.7580, "longitude": -73.9855},
    "radius_meters": 300
  }'

# Test rule parser
curl "http://localhost:8000/parking/rules/parse?rule_text=NO%20PARKING%208AM-6PM%20MON%20THRU%20FRI"
```
### 2. Test with Mock Data

Since OpenCurb only covers Midtown Manhattan (30th-59th St), you can test with these locations:

- Times Square: 40.7580, -73.9855
- Grand Central: 40.7527, -73.9772
- Penn Station: 40.7506, -73.9935
- Columbus Circle: 40.7685, -73.9818

### 3. Performance Testing

```bash
# Install Apache Bench
apt-get install apache2-utils  # Ubuntu
brew install httpd  # macOS

# Test API performance
ab -n 1000 -c 10 -T application/json -p query.json http://localhost:8000/parking/query
```

## Production Deployment

### Backend (AWS/GCP/Azure)

1. Dockerize the application:
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

2. Deploy to cloud:
- AWS: Use ECS or Elastic Beanstalk
- GCP: Use Cloud Run or App Engine
- Azure: Use Container Instances or App Service

### Database

- Use managed PostgreSQL with PostGIS:
  - AWS: RDS PostgreSQL with PostGIS
  - GCP: Cloud SQL PostgreSQL
  - Azure: Database for PostgreSQL

### Android App

1. Generate signed APK in Android Studio
2. Upload to Google Play Store
3. Or distribute via Firebase App Distribution

## Monitoring & Maintenance

### Logging
- Use structured logging with correlation IDs
- Integrate with CloudWatch, Stackdriver, or Azure Monitor

### Metrics to Track
- API response times
- Parking query accuracy
- User location tracking frequency
- Cache hit rates

### Data Updates
- Schedule daily updates from NYC Open Data
- Monitor OpenCurb API for coverage expansions
- Track parking rule changes

## Security Considerations

1. **API Security**
   - Implement rate limiting
   - Add API key authentication
   - Use HTTPS in production

2. **Privacy**
   - Don't store user location history
   - Anonymize usage analytics
   - Comply with GDPR/CCPA

3. **Android App**
   - Obfuscate API endpoints
   - Certificate pinning for HTTPS
   - Request minimal permissions