package com.nycparking.navigator

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.google.android.gms.location.*
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.maps.android.compose.*
import com.nycparking.navigator.ui.theme.NYCParkingNavigatorTheme
import kotlinx.coroutines.delay
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

class MainActivity : ComponentActivity() {
    
    private lateinit var fusedLocationClient: FusedLocationProviderClient
    private lateinit var parkingApi: ParkingApiService
    
    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted: Boolean ->
        if (isGranted) {
            // Permission granted
        } else {
            Toast.makeText(this, "Location permission required", Toast.LENGTH_LONG).show()
        }
    }
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Initialize location client
        fusedLocationClient = LocationServices.getFusedLocationProviderClient(this)
        
        // Initialize API client with fallback URL
        val retrofit = Retrofit.Builder()
            .baseUrl(BuildConfig.LOCAL_API_URL) // Use local for demo
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            
        parkingApi = retrofit.create(ParkingApiService::class.java)
        
        // Check location permission
        when {
            ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.ACCESS_FINE_LOCATION
            ) == PackageManager.PERMISSION_GRANTED -> {
                // Permission already granted
            }
            else -> {
                requestPermissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
            }
        }
        
        setContent {
            NYCParkingNavigatorTheme {
                ParkingNavigatorApp()
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ParkingNavigatorApp() {
    var showAudioEnabled by remember { mutableStateOf(false) }
    val context = LocalContext.current
    
    // Default to Times Square
    val timesSquare = LatLng(40.7580, -73.9855)
    val cameraPositionState = rememberCameraPositionState {
        position = CameraPosition.fromLatLngZoom(timesSquare, 16f)
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("NYC Parking Navigator") },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer
                )
            )
        },
        floatingActionButton = {
            Column {
                // Audio toggle
                FloatingActionButton(
                    onClick = { 
                        showAudioEnabled = !showAudioEnabled
                        Toast.makeText(
                            context, 
                            if (showAudioEnabled) "Audio navigation enabled" else "Audio navigation disabled",
                            Toast.LENGTH_SHORT
                        ).show()
                    },
                    modifier = Modifier.padding(bottom = 16.dp),
                    containerColor = if (showAudioEnabled) 
                        MaterialTheme.colorScheme.primary 
                    else 
                        MaterialTheme.colorScheme.secondary
                ) {
                    Text(if (showAudioEnabled) "🔊" else "🔇", style = MaterialTheme.typography.headlineMedium)
                }
                
                // Location button
                ExtendedFloatingActionButton(
                    onClick = { 
                        Toast.makeText(context, "Getting current location...", Toast.LENGTH_SHORT).show()
                    },
                    text = { Text("My Location") },
                    icon = { Text("📍") }
                )
            }
        }
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            // Google Map
            GoogleMap(
                modifier = Modifier.fillMaxSize(),
                cameraPositionState = cameraPositionState,
                properties = MapProperties(
                    isMyLocationEnabled = true
                ),
                uiSettings = MapUiSettings(
                    zoomControlsEnabled = true,
                    myLocationButtonEnabled = true
                )
            ) {
                // Add parking overlays here
                // For demo, just show the map
            }
            
            // Info card
            Card(
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .padding(16.dp)
                    .fillMaxWidth(),
                elevation = CardDefaults.cardElevation(defaultElevation = 8.dp)
            ) {
                Column(
                    modifier = Modifier.padding(16.dp)
                ) {
                    Text(
                        "Welcome to NYC Parking Navigator!",
                        style = MaterialTheme.typography.titleMedium
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        "• Tap anywhere on the map to see parking rules\n" +
                        "• Use audio navigation for hands-free guidance\n" +
                        "• Real-time parking availability",
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }
            
            // Demo notice
            if (BuildConfig.LOCAL_API_URL.contains("10.0.2.2")) {
                Card(
                    modifier = Modifier
                        .align(Alignment.BottomCenter)
                        .padding(16.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer
                    )
                ) {
                    Text(
                        "Demo Mode - Using local server",
                        modifier = Modifier.padding(8.dp),
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
        }
    }
}