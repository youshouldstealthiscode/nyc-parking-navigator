"""
Unit tests for NYC Parking Navigator
"""
import pytest
import asyncio
from datetime import datetime, time, timedelta
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock

from main import app, parser, parking_service, Location, ParkingQuery
from exceptions import ValidationException, ExternalAPIException
from services import OpenCurbClient


# Test fixtures
@pytest.fixture
def client():
    """Test client for FastAPI app"""
    return TestClient(app)


@pytest.fixture
def sample_location():
    """Sample location in Times Square"""
    return Location(latitude=40.7580, longitude=-73.9855)


@pytest.fixture
def sample_opencurb_response():
    """Sample OpenCurb API response"""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-73.9855, 40.7580], [-73.9856, 40.7581]]
                },
                "properties": {
                    "id": "test-segment-1",
                    "street_name": "W 42nd St",
                    "side": "north",
                    "regulations": [
                        {"description": "NO PARKING 8AM-6PM MON THRU FRI"}
                    ]
                }
            }
        ]
    }


class TestParkingRuleParser:
    """Test parking rule parser"""
    
    @pytest.mark.asyncio
    async def test_parse_simple_rule(self):
        """Test parsing simple no parking rule"""
        rule = "NO PARKING 8AM-6PM MON THRU FRI"
        result = await parser.parse_rule(rule)
        
        assert result['type'] == 'NO_PARKING'
        assert result['days'] == [0, 1, 2, 3, 4]  # Monday through Friday
        assert result['time_range'] is not None
        assert result['parsed'] is True
        
    @pytest.mark.asyncio
    async def test_parse_metered_parking(self):
        """Test parsing metered parking rule"""
        rule = "2 HOUR PARKING 9AM-7PM EXCEPT SUNDAY"
        result = await parser.parse_rule(rule)
        
        assert result['type'] == 'METERED'
        assert result['hours_limit'] == 2
        assert 6 in result['exceptions']  # Sunday
        
    @pytest.mark.asyncio
    async def test_parse_street_cleaning(self):
        """Test parsing street cleaning rule"""
        rule = "NO PARKING 11AM-12:30PM TUE & FRI STREET CLEANING"
        result = await parser.parse_rule(rule)
        
        assert result['type'] == 'STREET_CLEANING'
        assert result['days'] == [1, 4]  # Tuesday and Friday
        
    def test_parse_time_range(self):
        """Test time range parsing"""
        assert parser.parse_time_range("8AM-6PM") == (time(8, 0), time(18, 0))
        assert parser.parse_time_range("11:30AM-1:00PM") == (time(11, 30), time(13, 0))
        assert parser.parse_time_range("10PM-2AM") == (time(22, 0), time(2, 0))
        
    def test_parse_days(self):
        """Test day parsing"""
        assert parser.parse_days("MON THRU FRI") == [0, 1, 2, 3, 4]
        assert parser.parse_days("TUE & THU") == [1, 3]
        assert parser.parse_days("SATURDAY") == [5]
        assert parser.parse_days("MON,WED,FRI") == [0, 2, 4]


class TestParkingService:
    """Test parking service business logic"""
    
    @pytest.mark.asyncio
    async def test_check_parking_weekday_restriction(self):
        """Test parking check during restricted hours"""
        regulations = [
            {"description": "NO PARKING 8AM-6PM MON THRU FRI"}
        ]
        
        # Monday at 2 PM - should be restricted
        check_time = datetime(2024, 1, 8, 14, 0)  # Monday
        allowed, restriction, confidence = await parking_service.check_parking_availability(
            regulations, check_time
        )
        
        assert allowed is False
        assert restriction == 'NO_PARKING'
        
    @pytest.mark.asyncio
    async def test_check_parking_weekend_allowed(self):
        """Test parking check on weekend"""
        regulations = [
            {"description": "NO PARKING 8AM-6PM MON THRU FRI"}
        ]
        
        # Saturday at 2 PM - should be allowed
        check_time = datetime(2024, 1, 13, 14, 0)  # Saturday
        allowed, restriction, confidence = await parking_service.check_parking_availability(
            regulations, check_time
        )
        
        assert allowed is True
        assert restriction is None


class TestAPI:
    """Test API endpoints"""
    
    def test_health_check(self, client):
        """Test health endpoint"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert 'version' in data
        
    def test_parse_rule_endpoint(self, client):
        """Test rule parsing endpoint"""
        response = client.get(
            "/api/v1/parking/rules/parse",
            params={"rule_text": "NO PARKING 8AM-6PM"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['type'] == 'NO_PARKING'
        
    def test_parse_rule_empty(self, client):
        """Test parsing empty rule"""
        response = client.get(
            "/api/v1/parking/rules/parse",
            params={"rule_text": ""}
        )
        assert response.status_code == 422  # Validation error
        
    @pytest.mark.asyncio
    async def test_parking_query(self, client, sample_location, monkeypatch):
        """Test parking query endpoint"""
        # Mock OpenCurb response
        mock_response = {
            "type": "FeatureCollection",
            "features": []
        }
        
        async def mock_get_parking_data(*args, **kwargs):
            return mock_response['features']
            
        monkeypatch.setattr(
            "services.OpenCurbClient.get_parking_data",
            mock_get_parking_data
        )
        
        response = client.post(
            "/api/v1/parking/query",
            json={
                "location": {
                    "latitude": sample_location.latitude,
                    "longitude": sample_location.longitude
                },
                "radius_meters": 200
            }
        )
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)