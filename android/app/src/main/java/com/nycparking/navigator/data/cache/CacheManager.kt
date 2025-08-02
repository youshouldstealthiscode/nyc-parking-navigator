package com.nycparking.navigator.data.cache

import android.content.SharedPreferences
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class CacheManager @Inject constructor(
    private val sharedPreferences: SharedPreferences,
    private val gson: Gson
) {
    companion object {
        const val PARKING_DATA_TTL = 5L // 5 minutes
        private const val CACHE_PREFIX = "cache_"
        private const val EXPIRY_PREFIX = "expiry_"
    }
    
    inline fun <reified T> get(key: String): T? {
        val fullKey = CACHE_PREFIX + key
        val expiryKey = EXPIRY_PREFIX + key
        
        // Check expiry
        val expiryTime = sharedPreferences.getLong(expiryKey, 0)
        if (System.currentTimeMillis() > expiryTime) {
            // Cache expired, remove it
            remove(key)
            return null
        }
        
        // Get cached data
        val json = sharedPreferences.getString(fullKey, null) ?: return null
        
        return try {
            val type = object : TypeToken<T>() {}.type
            gson.fromJson<T>(json, type)
        } catch (e: Exception) {
            null
        }
    }
    
    fun <T> put(key: String, value: T, ttlMinutes: Long = PARKING_DATA_TTL) {
        val fullKey = CACHE_PREFIX + key
        val expiryKey = EXPIRY_PREFIX + key
        
        val json = gson.toJson(value)
        val expiryTime = System.currentTimeMillis() + TimeUnit.MINUTES.toMillis(ttlMinutes)
        
        sharedPreferences.edit().apply {
            putString(fullKey, json)
            putLong(expiryKey, expiryTime)
            apply()
        }
    }
    
    fun remove(key: String) {
        val fullKey = CACHE_PREFIX + key
        val expiryKey = EXPIRY_PREFIX + key
        
        sharedPreferences.edit().apply {
            remove(fullKey)
            remove(expiryKey)
            apply()
        }
    }
    
    fun clear() {
        val editor = sharedPreferences.edit()
        
        sharedPreferences.all.keys
            .filter { it.startsWith(CACHE_PREFIX) || it.startsWith(EXPIRY_PREFIX) }
            .forEach { editor.remove(it) }
            
        editor.apply()
    }
    
    fun clearExpired() {
        val currentTime = System.currentTimeMillis()
        val editor = sharedPreferences.edit()
        val keysToRemove = mutableListOf<String>()
        
        sharedPreferences.all.entries
            .filter { it.key.startsWith(EXPIRY_PREFIX) }
            .forEach { entry ->
                val expiryTime = entry.value as? Long ?: 0
                if (currentTime > expiryTime) {
                    val baseKey = entry.key.removePrefix(EXPIRY_PREFIX)
                    keysToRemove.add(baseKey)
                }
            }
            
        keysToRemove.forEach { key ->
            editor.remove(CACHE_PREFIX + key)
            editor.remove(EXPIRY_PREFIX + key)
        }
        
        editor.apply()
    }
}