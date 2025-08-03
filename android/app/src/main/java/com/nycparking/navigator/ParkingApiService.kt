package com.nycparking.navigator

import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Body
import retrofit2.http.Query

interface ParkingApiService {
    @POST("api/v1/parking/query")
    suspend fun queryParking(@Body request: ParkingQueryRequest): List<ParkingSegment>
    
    @GET("api/v1/parking/location/{lat}/{lon}")
    suspend fun getParkingAtLocation(
        @Query("lat") latitude: Double,
        @Query("lon") longitude: Double,
        @Query("radius") radius: Int = 200
    ): List<ParkingSegment>
}

data class ParkingQueryRequest(
    val location: Location,
    val radius_meters: Int = 300
)

data class Location(
    val latitude: Double,
    val longitude: Double
)

data class ParkingSegment(
    val segment_id: String,
    val street_name: String,
    val side: String,
    val current_status: String,
    val status_color: String,
    val regulations: List<Regulation>,
    val distance: Double
)

data class Regulation(
    val description: String
)