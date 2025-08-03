"""
Intelligent Audio Navigation System
Provides context-aware parking announcements
"""
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
from geopy.distance import distance

from logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class AudioAnnouncement:
    """Represents an audio announcement"""
    text: str
    priority: int  # 1-5, higher is more important
    category: str  # 'navigation', 'alert', 'reminder', 'prediction'
    expires_at: Optional[datetime] = None


class ParkingAudioNavigator:
    """Intelligent audio navigation for parking"""
    
    def __init__(self):
        self.last_announcement = None
        self.last_street = None
        self.announcement_cooldown = 10  # seconds between similar announcements
        self.last_announcement_time = {}
        
    def generate_zone_announcement(
        self,
        current_street: str,
        left_side_segments: List[Dict],
        right_side_segments: List[Dict],
        current_time: datetime
    ) -> Optional[AudioAnnouncement]:
        """Generate announcement when entering a new parking zone"""
        
        # Don't repeat for same street
        if current_street == self.last_street:
            return None
            
        self.last_street = current_street
        
        # Analyze parking availability
        left_status = self._analyze_side(left_side_segments, current_time)
        right_status = self._analyze_side(right_side_segments, current_time)
        
        # Generate natural language announcement
        announcement_parts = [f"Now on {current_street}."]
        
        # Describe each side
        if left_status['all_available']:
            announcement_parts.append("Left side completely open.")
        elif left_status['all_restricted']:
            announcement_parts.append("No parking left side.")
        elif left_status['available_spots'] > 0:
            announcement_parts.append(f"Left side has parking for {left_status['available_spots']} blocks.")
            
        if right_status['all_available']:
            announcement_parts.append("Right side completely open.")
        elif right_status['all_restricted']:
            announcement_parts.append("No parking right side.")
        elif right_status['available_spots'] > 0:
            announcement_parts.append(f"Right side has parking for {right_status['available_spots']} blocks.")
            
        # Add time-based warnings
        warnings = []
        if left_status['restriction_ends_soon']:
            warnings.append(f"Left side opens in {left_status['minutes_until_available']} minutes.")
        if right_status['restriction_ends_soon']:
            warnings.append(f"Right side opens in {right_status['minutes_until_available']} minutes.")
            
        if warnings:
            announcement_parts.extend(warnings)
            
        # Special conditions
        if left_status['street_cleaning_active'] or right_status['street_cleaning_active']:
            announcement_parts.append("Street cleaning in progress.")
            
        # Optimize announcement
        announcement_text = " ".join(announcement_parts)
        
        return AudioAnnouncement(
            text=announcement_text,
            priority=3,
            category='navigation'
        )
    
    def _analyze_side(self, segments: List[Dict], current_time: datetime) -> Dict:
        """Analyze parking availability for one side of street"""
        if not segments:
            return {
                'all_available': False,
                'all_restricted': False,
                'available_spots': 0,
                'restriction_ends_soon': False,
                'minutes_until_available': None,
                'street_cleaning_active': False
            }
            
        available_count = sum(1 for s in segments if s.get('status_color') == 'green')
        restricted_count = sum(1 for s in segments if s.get('status_color') == 'red')
        
        # Check if restrictions end soon
        restriction_ends_soon = False
        minutes_until_available = None
        
        for segment in segments:
            if segment.get('next_change'):
                next_change = datetime.fromisoformat(segment['next_change'])
                time_diff = (next_change - current_time).total_seconds() / 60
                
                if 0 < time_diff < 30 and segment.get('status_color') == 'red':
                    restriction_ends_soon = True
                    minutes_until_available = int(time_diff)
                    break
                    
        # Check for street cleaning
        street_cleaning = any(
            'STREET CLEANING' in r.get('description', '').upper()
            for s in segments
            for r in s.get('regulations', [])
        )
        
        return {
            'all_available': available_count == len(segments),
            'all_restricted': restricted_count == len(segments),
            'available_spots': available_count,
            'restriction_ends_soon': restriction_ends_soon,
            'minutes_until_available': minutes_until_available,
            'street_cleaning_active': street_cleaning
        }
    
    def generate_predictive_announcement(
        self,
        upcoming_segments: List[Dict],
        current_location: Tuple[float, float],
        current_speed: float
    ) -> Optional[AudioAnnouncement]:
        """Generate predictive announcements about upcoming parking"""
        
        # Find spots that will become available soon
        predictions = []
        
        for segment in upcoming_segments:
            if segment.get('next_change') and segment.get('status_color') == 'red':
                next_change = datetime.fromisoformat(segment['next_change'])
                time_until_available = (next_change - datetime.now()).total_seconds()
                
                # Calculate distance to segment
                if segment.get('coordinates'):
                    seg_location = (segment['coordinates'][0][1], segment['coordinates'][0][0])
                    dist = distance(current_location, seg_location).meters
                    
                    # Estimate arrival time based on speed
                    if current_speed > 0:
                        arrival_time = dist / current_speed
                        
                        # If we'll arrive just as it becomes available
                        if abs(arrival_time - time_until_available) < 60:
                            predictions.append({
                                'street': segment.get('street_name'),
                                'side': segment.get('side'),
                                'minutes': int(time_until_available / 60)
                            })
                            
        if predictions:
            best = predictions[0]
            return AudioAnnouncement(
                text=f"Parking opening soon: {best['street']} {best['side']} side in {best['minutes']} minutes.",
                priority=2,
                category='prediction'
            )
            
        return None
    
    def generate_alert_announcement(
        self,
        current_parking_spot: Optional[Dict],
        current_time: datetime
    ) -> Optional[AudioAnnouncement]:
        """Generate alerts for current parking spot"""
        
        if not current_parking_spot:
            return None
            
        # Check if restriction is about to start
        regulations = current_parking_spot.get('regulations', [])
        for reg in regulations:
            # Parse regulation to check if restriction starts soon
            # This would use the parking rule parser
            pass
            
        # Street cleaning reminder
        if self._is_street_cleaning_tomorrow(current_parking_spot, current_time):
            return AudioAnnouncement(
                text="Reminder: Street cleaning tomorrow morning. Move your car by 8 AM.",
                priority=4,
                category='alert'
            )
            
        return None
    
    def _is_street_cleaning_tomorrow(self, spot: Dict, current_time: datetime) -> bool:
        """Check if street cleaning is scheduled for tomorrow"""
        tomorrow = current_time + timedelta(days=1)
        tomorrow_weekday = tomorrow.weekday()
        
        for reg in spot.get('regulations', []):
            desc = reg.get('description', '').upper()
            if 'STREET CLEANING' in desc:
                # Parse days from regulation
                # This is simplified - would use full parser
                days_map = {'MON': 0, 'TUE': 1, 'WED': 2, 'THU': 3, 'FRI': 4}
                for day, num in days_map.items():
                    if day in desc and num == tomorrow_weekday:
                        return True
                        
        return False
    
    def should_announce(self, announcement: AudioAnnouncement) -> bool:
        """Determine if announcement should be made based on cooldown and priority"""
        
        key = f"{announcement.category}:{announcement.text[:20]}"
        last_time = self.last_announcement_time.get(key, 0)
        current_time = datetime.now().timestamp()
        
        # High priority announcements always go through
        if announcement.priority >= 4:
            self.last_announcement_time[key] = current_time
            return True
            
        # Check cooldown for lower priority
        if current_time - last_time > self.announcement_cooldown:
            self.last_announcement_time[key] = current_time
            return True
            
        return False