package com.nycparking.navigator

import android.app.Application
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class ParkingNavigatorApp : Application() {
    
    override fun onCreate() {
        super.onCreate()
        
        // Initialize any app-wide components here
    }
}