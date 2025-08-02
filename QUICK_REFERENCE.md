# NYC Parking Navigator - Quick Reference

## 🚀 Start Everything
```bash
cd /Users/joesmbp/Projects/nyc-parking-navigator
./setup.sh
```

## 🔗 Access Points
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Dashboard**: http://localhost:8080

## 🧪 Test Locations (Midtown Manhattan)
```
Times Square:    40.7580, -73.9855
Grand Central:   40.7527, -73.9772
Penn Station:    40.7506, -73.9935
Columbus Circle: 40.7685, -73.9818
```

## 🎨 Color Codes
- 🟢 **Green**: Parking available
- 🔴 **Red**: No parking/restricted
- 🔵 **Blue**: Metered parking
- 🟡 **Yellow**: Loading zone

## 📱 Android Setup
1. Open `android/` folder in Android Studio
2. Update server IP in MainActivity.kt
3. Add Google Maps API key
4. Run on device/emulator

## 🛠️ Common Commands
```bash
# Run tests
cd backend && python test_api.py

# Run demo
python demo.py

# Check logs
tail -f backend/backend.log

# Stop all services
pkill -f uvicorn
pkill -f "python3 -m http.server"
```

## 📡 API Examples
```bash
# Check parking at location
curl -X POST http://localhost:8000/parking/query \
  -H "Content-Type: application/json" \
  -d '{"location": {"latitude": 40.7580, "longitude": -73.9855}}'

# Parse a parking sign
curl "http://localhost:8000/parking/rules/parse?rule_text=NO%20PARKING%208AM-6PM"
```

## 🐛 Troubleshooting
- **Backend not starting**: Check if port 8000 is in use
- **No parking data**: Verify you're testing in Midtown Manhattan
- **Dashboard blank**: Ensure backend is running first

## 📚 Documentation
- Full README: `/README.md`
- Deployment: `/DEPLOYMENT.md`
- Project Summary: `/PROJECT_SUMMARY.md`

---
Happy Parking! 🚗✨