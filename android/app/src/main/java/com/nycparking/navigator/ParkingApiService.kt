package com.nycparking.navigator

import retrofit2.http.*

// Data classes
data class LocationData(
    val latitude: Double,
    val longitude: Double
)

data class ParkingQuery(
    val location: LocationData,
    val radiusMeters: Int = 500,
    val queryTime: String? = null
)

data class ParkingSegment(
    val segmentId: String,
    val coordinates: List<List<Double>>,
    val streetName: String,
    val side: String,
    val regulations: List<Map<String, Any>>,
    val currentStatus: String,
    val statusColor: String,
    val nextChange: String?
)

// API Service
interface ParkingApiService {
    @POST("parking/query")
    suspend fun queryParking(@Body query: ParkingQuery): List<ParkingSegment>
    
    @GET("parking/location/{lat}/{lon}")
    suspend fun getParkingAtLocation(
        @Path("lat") lat: Double,
        @Path("lon") lon: Double,
        @Query("radius") radius: Int = 200
    ): List<ParkingSegment>
    
    @GET("health")
    suspend fun healthCheck(): Map<String, Any>
}