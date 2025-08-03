#!/bin/bash
# NYC Parking Navigator - Easy Setup Script
# Gets everything running in minutes!

echo "🚗 NYC Parking Navigator - Personal Setup"
echo "========================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required. Please install it first."
    exit 1
fi

# Check if running on Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    MODEL=$(cat /proc/device-tree/model)
    if [[ $MODEL == *"Raspberry Pi"* ]]; then
        echo "🥧 Detected Raspberry Pi! Optimizing for Pi..."
        export LIGHTWEIGHT_MODE=1
    fi
fi

echo "📦 Installing dependencies..."
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install minimal requirements
pip install fastapi uvicorn requests sqlite3 pydantic

echo ""
echo "📊 Downloading NYC parking data..."
echo "This will download 1.2M+ parking signs (~200MB)"
read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    cd scripts
    python3 download_nyc_data.py
    cd ..
else
    echo "⚠️  Skipping data download. You can run it later with:"
    echo "   python3 backend/scripts/download_nyc_data.py"
fi

echo ""
echo "🚀 Starting backend server..."

# Get local IP
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    LOCAL_IP=$(ipconfig getifaddr en0 || ipconfig getifaddr en1)
else
    # Linux/Pi
    LOCAL_IP=$(hostname -I | awk '{print $1}')
fi

echo ""
echo "✅ Backend starting at:"
echo "   Local:  http://localhost:8000"
echo "   Network: http://${LOCAL_IP}:8000"
echo ""
echo "📱 Configure your app with: http://${LOCAL_IP}:8000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server
python3 backend_simple.py