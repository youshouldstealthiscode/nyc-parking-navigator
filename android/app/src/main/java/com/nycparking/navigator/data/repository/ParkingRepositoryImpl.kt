package com.nycparking.navigator.data.repository

import com.nycparking.navigator.data.api.ParkingApiService
import com.nycparking.navigator.data.model.*
import com.nycparking.navigator.domain.model.ParkingSegmentDomain
import com.nycparking.navigator.domain.repository.ParkingRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ParkingRepositoryImpl @Inject constructor(
    private val apiService: ParkingApiService,
    private val cacheManager: CacheManager
) : ParkingRepository {
    
    override suspend fun queryParking(
        latitude: Double,
        longitude: Double,
        radiusMeters: Int,
        queryTime: String?
    ): Result<List<ParkingSegmentDomain>> = withContext(Dispatchers.IO) {
        try {
            // Check cache first
            val cacheKey = "$latitude:$longitude:$radiusMeters:${queryTime ?: "current"}"
            cacheManager.get<List<ParkingSegment>>(cacheKey)?.let { cached ->
                return@withContext Result.success(cached.map { it.toDomain() })
            }
            
            // Make API call
            val query = ParkingQuery(
                location = LocationData(latitude, longitude),
                radiusMeters = radiusMeters,
                queryTime = queryTime
            )
            
            val response = apiService.queryParking(query)
            
            // Cache the result
            cacheManager.put(cacheKey, response, CacheManager.PARKING_DATA_TTL)
            
            // Map to domain model
            Result.success(response.map { it.toDomain() })
            
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    override suspend fun getParkingAtLocation(
        latitude: Double,
        longitude: Double,
        radius: Int
    ): Result<List<ParkingSegmentDomain>> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getParkingAtLocation(latitude, longitude, radius)
            Result.success(response.map { it.toDomain() })
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
    
    override suspend fun checkHealth(): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.healthCheck()
            Result.success(response["status"] == "healthy")
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}

// Extension function to map data model to domain model
private fun ParkingSegment.toDomain(): ParkingSegmentDomain {
    return ParkingSegmentDomain(
        segmentId = segmentId,
        coordinates = coordinates,
        streetName = streetName,
        side = side,
        regulations = regulations,
        currentStatus = currentStatus,
        statusColor = statusColor,
        nextChange = nextChange,
        distance = distance
    )
}