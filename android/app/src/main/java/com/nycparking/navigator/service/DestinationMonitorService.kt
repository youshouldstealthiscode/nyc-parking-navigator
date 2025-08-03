package com.nycparking.navigator.service

import android.app.*
import android.content.Intent
import android.location.Location
import android.os.Build
import android.os.IBinder
import android.speech.tts.TextToSpeech
import androidx.core.app.NotificationCompat
import com.google.android.gms.location.*
import com.nycparking.navigator.MainActivity
import com.nycparking.navigator.R
import java.util.*
import kotlin.math.*

class DestinationMonitorService : Service(), TextToSpeech.OnInitListener {
    
    companion object {
        const val CHANNEL_ID = "destination_monitor"
        const val NOTIFICATION_ID = 1001
        const val ACTION_START_MONITORING = "start_monitoring"
        const val ACTION_STOP_MONITORING = "stop_monitoring"
        const val EXTRA_DEST_LAT = "dest_lat"
        const val EXTRA_DEST_LON = "dest_lon"
        const val EXTRA_THRESHOLD = "threshold_meters"
    }
    
    private lateinit var fusedLocationClient: FusedLocationProviderClient
    private lateinit var locationCallback: LocationCallback
    private var textToSpeech: TextToSpeech? = null
    
    private var destinationLat: Double = 0.0
    private var destinationLon: Double = 0.0
    private var thresholdMeters: Float = 800f // Default 0.5 miles
    private var hasTriggered = false
    
    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        fusedLocationClient = LocationServices.getFusedLocationProviderClient(this)
        textToSpeech = TextToSpeech(this, this)
        
        setupLocationCallback()
    }
    
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START_MONITORING -> {
                destinationLat = intent.getDoubleExtra(EXTRA_DEST_LAT, 0.0)
                destinationLon = intent.getDoubleExtra(EXTRA_DEST_LON, 0.0)
                thresholdMeters = intent.getFloatExtra(EXTRA_THRESHOLD, 800f)
                
                startForeground(NOTIFICATION_ID, createNotification())
                startLocationUpdates()
            }
            ACTION_STOP_MONITORING -> {
                stopLocationUpdates()
                stopForeground(true)
                stopSelf()
            }
        }
        
        return START_STICKY
    }
    
    private fun setupLocationCallback() {
        locationCallback = object : LocationCallback() {
            override fun onLocationResult(locationResult: LocationResult) {
                locationResult.lastLocation?.let { location ->
                    checkProximityToDestination(location)
                }
            }
        }
    }
    
    private fun checkProximityToDestination(currentLocation: Location) {
        val distance = calculateDistance(
            currentLocation.latitude,
            currentLocation.longitude,
            destinationLat,
            destinationLon
        )
        
        // Update notification with distance
        updateNotification(distance)
        
        // Check if within threshold and haven't triggered yet
        if (distance <= thresholdMeters && !hasTriggered) {
            hasTriggered = true
            triggerParkingMode(distance)
        }
    }
    
    private fun triggerParkingMode(distanceMeters: Float) {
        // Calculate ETA (assuming average speed of 30 mph in city)
        val speedMps = 13.4 // 30 mph in m/s
        val etaSeconds = (distanceMeters / speedMps).toInt()
        val etaMinutes = etaSeconds / 60
        
        // Voice announcement
        val announcement = buildString {
            append("Approaching destination. ")
            append("${etaMinutes} minutes remaining. ")
            append("${distanceMeters.toInt()} meters to go. ")
            append("Launching parking navigator.")
        }
        
        textToSpeech?.speak(announcement, TextToSpeech.QUEUE_FLUSH, null, "arrival")
        
        // Launch app in parking mode
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra("parking_mode", true)
            putExtra("destination_lat", destinationLat)
            putExtra("destination_lon", destinationLon)
        }
        startActivity(intent)
        
        // Stop monitoring after trigger
        stopSelf()
    }
    
    private fun calculateDistance(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Float {
        val r = 6371000.0 // Earth radius in meters
        val dLat = Math.toRadians(lat2 - lat1)
        val dLon = Math.toRadians(lon2 - lon1)
        
        val a = sin(dLat / 2).pow(2) + 
                cos(Math.toRadians(lat1)) * cos(Math.toRadians(lat2)) * 
                sin(dLon / 2).pow(2)
        val c = 2 * atan2(sqrt(a), sqrt(1 - a))
        
        return (r * c).toFloat()
    }
    
    private fun startLocationUpdates() {
        val locationRequest = LocationRequest.create().apply {
            interval = 10000 // 10 seconds
            fastestInterval = 5000 // 5 seconds
            priority = LocationRequest.PRIORITY_HIGH_ACCURACY
        }
        
        try {
            fusedLocationClient.requestLocationUpdates(
                locationRequest,
                locationCallback,
                mainLooper
            )
        } catch (e: SecurityException) {
            // Handle permission error
        }
    }
    
    private fun stopLocationUpdates() {
        fusedLocationClient.removeLocationUpdates(locationCallback)
    }
    
    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Destination Monitor",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Monitors proximity to destination for parking"
            }
            
            val notificationManager = getSystemService(NotificationManager::class.java)
            notificationManager.createNotificationChannel(channel)
        }
    }
    
    private fun createNotification(): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Monitoring destination")
            .setContentText("Will launch parking mode when close")
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setOngoing(true)
            .build()
    }
    
    private fun updateNotification(distanceMeters: Float) {
        val distanceText = when {
            distanceMeters > 1000 -> "%.1f km away".format(distanceMeters / 1000)
            else -> "${distanceMeters.toInt()} meters away"
        }
        
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Approaching destination")
            .setContentText(distanceText)
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setOngoing(true)
            .build()
            
        val notificationManager = getSystemService(NotificationManager::class.java)
        notificationManager.notify(NOTIFICATION_ID, notification)
    }
    
    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            textToSpeech?.language = Locale.US
        }
    }
    
    override fun onBind(intent: Intent?): IBinder? = null
    
    override fun onDestroy() {
        super.onDestroy()
        stopLocationUpdates()
        textToSpeech?.shutdown()
    }
}