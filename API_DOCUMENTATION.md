# NYC Parking Navigator API Documentation

## Base URL
```
https://api.nycparking.app/api/v1
```

## Authentication
Currently, the API is open access. API key authentication is planned for production.

## Rate Limiting
- 100 requests per hour per IP address
- Rate limit headers are included in responses

## Common Response Headers
```
X-Request-ID: Unique request identifier
X-RateLimit-Limit: Rate limit ceiling
X-RateLimit-Remaining: Requests remaining
X-RateLimit-Reset: Reset timestamp
```

## Endpoints

### Health Check
Check API health status.

```http
GET /health
```

**Response**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "cache_status": "healthy"
}
```

### Query Parking
Get parking segments for a location.

```http
POST /parking/query
Content-Type: application/json
```

**Request Body**
```json
{
  "location": {
    "latitude": 40.7580,
    "longitude": -73.9855
  },
  "radius_meters": 300,
  "query_time": "2024-01-15T14:00:00Z"
}
```

**Parameters**
- `location` (required): Geographic coordinates
  - `latitude`: -90 to 90
  - `longitude`: -180 to 180
- `radius_meters` (optional): Search radius (50-2000m, default: 500)
- `query_time` (optional): ISO 8601 timestamp (defaults to current time)

**Response**
```json
[
  {
    "segment_id": "seg_123",
    "coordinates": [[-73.9855, 40.7580], [-73.9856, 40.7581]],
    "street_name": "W 42nd St",
    "side": "north",
    "regulations": [
      {
        "description": "NO PARKING 8AM-6PM MON THRU FRI"
      }
    ],
    "current_status": "NO_PARKING",
    "status_color": "red",
    "next_change": "2024-01-15T18:00:00Z",
    "confidence_score": 0.95,
    "distance": 150.5
  }
]
```

**Status Codes**
- `200`: Success
- `400`: Invalid request
- `422`: Validation error
- `503`: External service unavailable

### Get Parking at Location
Simplified endpoint for location queries.

```http
GET /parking/location/{latitude}/{longitude}?radius=200
```

**Parameters**
- `latitude` (required): -90 to 90
- `longitude` (required): -180 to 180
- `radius` (optional): Search radius in meters (50-1000, default: 200)

**Response**
Same as Query Parking endpoint.

### Parse Parking Rule
Parse and analyze parking rule text.

```http
GET /parking/rules/parse?rule_text=NO%20PARKING%208AM-6PM%20MON%20THRU%20FRI
```

**Parameters**
- `rule_text` (required): URL-encoded parking rule text (max 500 chars)

**Response**
```json
{
  "original_text": "NO PARKING 8AM-6PM MON THRU FRI",
  "type": "NO_PARKING",
  "days": [0, 1, 2, 3, 4],
  "time_range": ["08:00:00", "18:00:00"],
  "exceptions": [],
  "parsed": true,
  "confidence": 0.9
}
```

**Rule Types**
- `NO_PARKING`: No parking allowed
- `NO_STANDING`: No standing allowed
- `NO_STOPPING`: No stopping allowed
- `STREET_CLEANING`: Street cleaning restriction
- `METERED`: Metered parking
- `UNKNOWN`: Could not determine type

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "message": "Human-readable error message",
    "type": "ErrorType",
    "details": {
      "field": "Additional context"
    }
  }
}
```

**Common Error Types**
- `ValidationException`: Input validation failed
- `ExternalAPIException`: External service error
- `DataNotFoundException`: Resource not found
- `RateLimitException`: Rate limit exceeded

## Data Models

### Location
```typescript
{
  latitude: number;   // -90 to 90
  longitude: number;  // -180 to 180
}
```

### ParkingSegment
```typescript
{
  segment_id: string;
  coordinates: number[][];  // GeoJSON LineString
  street_name: string;
  side: "north" | "south" | "east" | "west" | "left" | "right" | "unknown";
  regulations: Regulation[];
  current_status: string;
  status_color: "green" | "red" | "blue" | "yellow" | "gray";
  next_change?: string;  // ISO 8601
  confidence_score: number;  // 0-1
  distance?: number;  // meters from query point
}
```

## Coverage Areas

### Current Coverage
- **OpenCurb**: Midtown Manhattan (30th-59th Street)
  - Real-time parking regulations
  - High accuracy

### Planned Coverage
- **NYC Open Data**: All 5 boroughs
  - Complete parking sign database
  - Daily updates

## Best Practices

1. **Caching**: Responses are cached for 5 minutes. Include appropriate cache headers.

2. **Time Zones**: All times are in UTC. Convert to local time (America/New_York) for display.

3. **Coordinates**: Use 6 decimal places maximum for lat/lng.

4. **Error Handling**: Always check status codes and handle errors gracefully.

5. **Rate Limiting**: Implement exponential backoff when rate limited.

## SDKs and Examples

### cURL
```bash
curl -X POST https://api.nycparking.app/api/v1/parking/query \
  -H "Content-Type: application/json" \
  -d '{
    "location": {"latitude": 40.7580, "longitude": -73.9855},
    "radius_meters": 300
  }'
```

### JavaScript/TypeScript
```javascript
const response = await fetch('https://api.nycparking.app/api/v1/parking/query', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    location: { latitude: 40.7580, longitude: -73.9855 },
    radius_meters: 300
  })
});

const segments = await response.json();
```

### Python
```python
import requests

response = requests.post(
    'https://api.nycparking.app/api/v1/parking/query',
    json={
        'location': {'latitude': 40.7580, 'longitude': -73.9855},
        'radius_meters': 300
    }
)

segments = response.json()
```

## Changelog

### v1.0.0 (2024-01-15)
- Initial release
- OpenCurb integration
- Basic parking query endpoints
- Rule parsing

## Support

- GitHub Issues: https://github.com/youshouldstealthiscode/nyc-parking-navigator
- Email: support@nycparking.app