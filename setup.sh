#!/bin/bash
# NYC Parking Navigator - Quick Setup Script

echo "NYC Parking Navigator - Setup Script"
echo "==================================="

# Check Python version
echo "Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo "✅ Python $PYTHON_VERSION found"
else
    echo "❌ Python 3 not found. Please install Python 3.9 or later."
    exit 1
fi

# Setup backend
echo -e "\n1. Setting up backend..."
cd backend

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Start backend in background
echo -e "\n2. Starting backend server..."
nohup uvicorn main:app --reload --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
echo "✅ Backend started (PID: $BACKEND_PID)"
echo "   API docs available at: http://localhost:8000/docs"

# Wait for backend to start
echo "Waiting for backend to start..."
sleep 5

# Test backend
echo -e "\n3. Testing backend..."
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ Backend is running!"
else
    echo "❌ Backend failed to start. Check backend.log for errors."
fi

# Setup web dashboard
echo -e "\n4. Starting web dashboard..."
cd ../web-dashboard

# Start web server
python3 -m http.server 8080 > ../backend/dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo "✅ Dashboard started (PID: $DASHBOARD_PID)"
echo "   Dashboard available at: http://localhost:8080"

# Display next steps
echo -e "\n==================================="
echo "Setup complete! 🎉"
echo ""
echo "Services running:"
echo "- Backend API: http://localhost:8000"
echo "- API Docs: http://localhost:8000/docs"
echo "- Dashboard: http://localhost:8080"
echo ""
echo "To stop services:"
echo "  kill $BACKEND_PID $DASHBOARD_PID"
echo ""
echo "To run tests:"
echo "  cd backend && python test_api.py"
echo ""
echo "Logs available at:"
echo "- backend/backend.log"
echo "- backend/dashboard.log"