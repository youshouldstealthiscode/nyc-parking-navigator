package com.nycparking.navigator

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Color
import android.location.Location
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.lifecycle.lifecycleScope
import com.google.android.gms.location.*
import com.google.android.gms.maps.CameraUpdateFactory
import com.google.android.gms.maps.GoogleMap
import com.google.android.gms.maps.OnMapReadyCallback
import com.google.android.gms.maps.SupportMapFragment
import com.google.android.gms.maps.model.*
import kotlinx.coroutines.launch
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.*

class MainActivity : AppCompatActivity(), OnMapReadyCallback, TextToSpeech.OnInitListener {
    
    private lateinit var map: GoogleMap
    private lateinit var fusedLocationClient: FusedLocationProviderClient
    private lateinit var locationCallback: LocationCallback
    private lateinit var textToSpeech: TextToSpeech
    private lateinit var parkingApi: ParkingApiService
    
    private var currentLocation: Location? = null
    private var parkingOverlays = mutableListOf<Polyline>()
    private var lastAnnouncedStreet: String? = null
    companion object {
        private const val LOCATION_PERMISSION_REQUEST_CODE = 1
        private const val DEFAULT_ZOOM = 17f
        private const val PARKING_QUERY_RADIUS = 300 // meters
    }
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        
        // Initialize location services
        fusedLocationClient = LocationServices.getFusedLocationProviderClient(this)
        
        // Initialize TTS
        textToSpeech = TextToSpeech(this, this)
        
        // Initialize API client
        val retrofit = Retrofit.Builder()
            .baseUrl("http://YOUR_SERVER_IP:8000/") // Replace with actual server
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            
        parkingApi = retrofit.create(ParkingApiService::class.java)
        
        // Setup map
        val mapFragment = supportFragmentManager
            .findFragmentById(R.id.map) as SupportMapFragment
        mapFragment.getMapAsync(this)
        
        // Setup location callback
        locationCallback = object : LocationCallback() {
            override fun onLocationResult(locationResult: LocationResult) {
                locationResult.lastLocation?.let { location ->
                    currentLocation = location
                    updateParkingOverlay(location)
                    centerMapOnLocation(location)
                }
            }
        }
    }
    override fun onMapReady(googleMap: GoogleMap) {
        map = googleMap
        
        // Enable location layer if permission granted
        if (ActivityCompat.checkSelfPermission(
                this,
                Manifest.permission.ACCESS_FINE_LOCATION
            ) == PackageManager.PERMISSION_GRANTED
        ) {
            map.isMyLocationEnabled = true
            startLocationUpdates()
        } else {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.ACCESS_FINE_LOCATION),
                LOCATION_PERMISSION_REQUEST_CODE
            )
        }
        
        // Customize map style
        map.setMapStyle(
            MapStyleOptions.loadRawResourceStyle(this, R.raw.map_style)
        )
    }
    
    private fun startLocationUpdates() {
        val locationRequest = LocationRequest.create().apply {
            interval = 5000 // 5 seconds
            fastestInterval = 2000 // 2 seconds
            priority = LocationRequest.PRIORITY_HIGH_ACCURACY
        }
        
        if (ActivityCompat.checkSelfPermission(
                this,
                Manifest.permission.ACCESS_FINE_LOCATION
            ) == PackageManager.PERMISSION_GRANTED
        ) {
            fusedLocationClient.requestLocationUpdates(
                locationRequest,
                locationCallback,
                mainLooper
            )
        }
    }
    private fun updateParkingOverlay(location: Location) {
        lifecycleScope.launch {
            try {
                val query = ParkingQuery(
                    location = LocationData(location.latitude, location.longitude),
                    radiusMeters = PARKING_QUERY_RADIUS
                )
                
                val segments = parkingApi.queryParking(query)
                
                // Clear existing overlays
                parkingOverlays.forEach { it.remove() }
                parkingOverlays.clear()
                
                // Draw new overlays
                segments.forEach { segment ->
                    val polylineOptions = PolylineOptions()
                        .width(15f)
                        .color(getColorForStatus(segment.statusColor))
                        .geodesic(true)
                    
                    segment.coordinates.forEach { coord ->
                        polylineOptions.add(LatLng(coord[1], coord[0]))
                    }
                    
                    val polyline = map.addPolyline(polylineOptions)
                    parkingOverlays.add(polyline)
                    
                    // Voice announcement for available parking
                    if (segment.statusColor == "green" && 
                        segment.streetName != lastAnnouncedStreet) {
                        announceParking(segment.streetName, segment.side)
                        lastAnnouncedStreet = segment.streetName
                    }
                }
                
            } catch (e: Exception) {
                Toast.makeText(
                    this@MainActivity,
                    "Error updating parking data: ${e.message}",
                    Toast.LENGTH_SHORT
                ).show()
            }
        }
    }
    private fun getColorForStatus(statusColor: String): Int {
        return when (statusColor) {
            "green" -> Color.GREEN
            "red" -> Color.RED
            "blue" -> Color.BLUE
            "yellow" -> Color.YELLOW
            else -> Color.GRAY
        }
    }
    
    private fun centerMapOnLocation(location: Location) {
        val latLng = LatLng(location.latitude, location.longitude)
        map.animateCamera(CameraUpdateFactory.newLatLngZoom(latLng, DEFAULT_ZOOM))
    }
    
    private fun announceParking(streetName: String, side: String) {
        val announcement = "Parking available on $streetName, $side side"
        textToSpeech.speak(announcement, TextToSpeech.QUEUE_FLUSH, null, null)
    }
    
    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            textToSpeech.language = Locale.US
        }
    }
    
    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == LOCATION_PERMISSION_REQUEST_CODE) {
            if (grantResults.isNotEmpty() && 
                grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                onMapReady(map)
            }
        }
    }
    
    override fun onDestroy() {
        super.onDestroy()
        textToSpeech.shutdown()
        fusedLocationClient.removeLocationUpdates(locationCallback)
    }
}