"""
User-centric features for parking navigation
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy import Column, String, Float, DateTime, Boolean, Integer, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field
import uuid

Base = declarative_base()


# Database Models
class User(Base):
    """User account model"""
    __tablename__ = 'users'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    preferences = Column(JSON, default={})
    
    # Relationships
    favorite_spots = relationship("FavoriteSpot", back_populates="user")
    parking_history = relationship("ParkingHistory", back_populates="user")
    alerts = relationship("ParkingAlert", back_populates="user")


class FavoriteSpot(Base):
    """User's favorite parking spots"""
    __tablename__ = 'favorite_spots'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id'))
    name = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    street_name = Column(String)
    notes = Column(String)
    success_rate = Column(Float, default=0.0)  # How often user finds parking here
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="favorite_spots")


class ParkingHistory(Base):
    """User's parking history"""
    __tablename__ = 'parking_history'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id'))
    latitude = Column(Float)
    longitude = Column(Float)
    street_name = Column(String)
    segment_id = Column(String)
    parked_at = Column(DateTime, default=datetime.utcnow)
    departed_at = Column(DateTime, nullable=True)
    cost = Column(Float, nullable=True)
    notes = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)  # Photo of where they parked
    
    user = relationship("User", back_populates="parking_history")


class ParkingAlert(Base):
    """User alerts for parking events"""
    __tablename__ = 'parking_alerts'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id'))
    type = Column(String)  # 'street_cleaning', 'meter_expiry', 'restriction_start'
    trigger_time = Column(DateTime)
    location_lat = Column(Float)
    location_lon = Column(Float)
    message = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="alerts")


class CommunityReport(Base):
    """Community-reported parking information"""
    __tablename__ = 'community_reports'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id'))
    latitude = Column(Float)
    longitude = Column(Float)
    report_type = Column(String)  # 'spot_available', 'spot_taken', 'ticket_officer', 'construction'
    message = Column(String)
    photo_url = Column(String, nullable=True)
    expires_at = Column(DateTime)
    upvotes = Column(Integer, default=0)
    downvotes = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


# Pydantic Models for API
class UserPreferences(BaseModel):
    """User preferences"""
    audio_navigation: bool = True
    audio_volume: int = Field(default=80, ge=0, le=100)
    announce_predictions: bool = True
    announce_restrictions: bool = True
    alert_before_cleaning: int = Field(default=12, description="Hours before street cleaning")
    alert_before_meter: int = Field(default=15, description="Minutes before meter expires")
    preferred_walking_distance: int = Field(default=200, description="Max walking distance in meters")
    save_parking_history: bool = True
    share_anonymous_data: bool = True


class FavoriteSpotCreate(BaseModel):
    """Create a favorite spot"""
    name: str = Field(..., max_length=100)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    notes: Optional[str] = Field(None, max_length=500)


class ParkingSessionStart(BaseModel):
    """Start a parking session"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    street_name: str
    segment_id: Optional[str] = None
    notes: Optional[str] = None
    photo_base64: Optional[str] = None


class ParkingSessionEnd(BaseModel):
    """End a parking session"""
    session_id: str
    cost: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = None


class CommunityReportCreate(BaseModel):
    """Create a community report"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    report_type: str = Field(..., regex="^(spot_available|spot_taken|ticket_officer|construction)$")
    message: str = Field(..., max_length=200)
    photo_base64: Optional[str] = None
    expires_in_minutes: int = Field(default=30, ge=5, le=240)


class ParkingTimer(BaseModel):
    """Parking timer/reminder"""
    duration_minutes: int = Field(..., ge=1, le=480)  # Max 8 hours
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    reminder_before: int = Field(default=15, description="Minutes before expiry")
    notes: Optional[str] = None


class GarageComparison(BaseModel):
    """Nearby garage information"""
    name: str
    address: str
    distance_meters: float
    price_per_hour: float
    price_per_day: Optional[float]
    availability: str  # 'available', 'limited', 'full'
    rating: Optional[float] = Field(None, ge=0, le=5)
    

# Feature Services
class UserFeatureService:
    """Service for user-centric features"""
    
    def __init__(self, db_session):
        self.db = db_session
        
    async def get_smart_suggestions(
        self,
        user_id: str,
        current_location: tuple,
        destination: Optional[tuple] = None
    ) -> List[Dict]:
        """Get smart parking suggestions based on user history and preferences"""
        
        # Get user's successful parking spots near location
        favorites = self.db.query(FavoriteSpot).filter(
            FavoriteSpot.user_id == user_id
        ).all()
        
        suggestions = []
        for fav in favorites:
            dist = self._calculate_distance(
                current_location,
                (fav.latitude, fav.longitude)
            )
            if dist < 1000:  # Within 1km
                suggestions.append({
                    'type': 'favorite',
                    'name': fav.name,
                    'location': (fav.latitude, fav.longitude),
                    'distance': dist,
                    'success_rate': fav.success_rate,
                    'notes': fav.notes
                })
                
        # Add ML-based predictions here
        # Based on time of day, day of week, and historical data
        
        return sorted(suggestions, key=lambda x: x['distance'])
    
    async def predict_availability(
        self,
        segment_id: str,
        target_time: datetime
    ) -> Dict:
        """Predict parking availability using historical data"""
        
        # This would use ML model trained on historical parking data
        # For now, return mock prediction
        
        hour = target_time.hour
        weekday = target_time.weekday()
        
        # Simple heuristic
        if weekday < 5:  # Weekday
            if 8 <= hour <= 18:
                availability_chance = 0.3
            else:
                availability_chance = 0.7
        else:  # Weekend
            availability_chance = 0.6
            
        return {
            'segment_id': segment_id,
            'prediction_time': target_time.isoformat(),
            'availability_probability': availability_chance,
            'confidence': 0.75,
            'factors': {
                'day_of_week': 'high_impact' if weekday < 5 else 'low_impact',
                'time_of_day': 'high_impact' if 8 <= hour <= 18 else 'medium_impact',
                'historical_pattern': 'consistent'
            }
        }
    
    async def get_walking_route(
        self,
        parking_location: tuple,
        destination: tuple
    ) -> Dict:
        """Get walking directions from parking to destination"""
        
        # This would integrate with a routing service
        # For now, return simple calculation
        
        distance = self._calculate_distance(parking_location, destination)
        walking_time = distance / 80  # Assume 80m/min walking speed
        
        return {
            'distance_meters': distance,
            'duration_minutes': round(walking_time),
            'route_polyline': None,  # Would be actual route
            'instructions': [
                f"Walk {distance:.0f}m to destination",
                f"Approximately {walking_time:.0f} minute walk"
            ]
        }
    
    def _calculate_distance(self, point1: tuple, point2: tuple) -> float:
        """Calculate distance between two points in meters"""
        from geopy.distance import distance
        return distance(point1, point2).meters