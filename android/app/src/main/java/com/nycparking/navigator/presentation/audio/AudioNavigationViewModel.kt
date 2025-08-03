package com.nycparking.navigator.presentation.audio

import android.content.Context
import android.location.Location
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.nycparking.navigator.domain.repository.ParkingRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import java.util.*
import javax.inject.Inject

@HiltViewModel
class AudioNavigationViewModel @Inject constructor(
    private val parkingRepository: ParkingRepository,
    private val context: Context
) : ViewModel(), TextToSpeech.OnInitListener {
    
    private val _audioState = MutableStateFlow(AudioNavigationState())
    val audioState: StateFlow<AudioNavigationState> = _audioState.asStateFlow()
    
    private var textToSpeech: TextToSpeech? = null
    private var lastAnnouncedStreet: String? = null
    private var lastAnnouncementTime = 0L
    
    private val announcementCooldown = 10000L // 10 seconds
    
    init {
        initializeTextToSpeech()
    }
    
    private fun initializeTextToSpeech() {
        textToSpeech = TextToSpeech(context, this)
    }
    
    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            textToSpeech?.apply {
                language = Locale.US
                setSpeechRate(1.0f)
                setPitch(1.0f)
                
                setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(utteranceId: String?) {
                        _audioState.update { it.copy(isSpeaking = true) }
                    }
                    
                    override fun onDone(utteranceId: String?) {
                        _audioState.update { it.copy(isSpeaking = false) }
                    }
                    
                    override fun onError(utteranceId: String?) {
                        _audioState.update { it.copy(isSpeaking = false) }
                    }
                })
            }
            
            _audioState.update { it.copy(isInitialized = true) }
        }
    }
    
    fun processLocationUpdate(location: Location, heading: Float, speed: Float) {
        if (!_audioState.value.isEnabled) return
        
        viewModelScope.launch {
            // Get audio navigation from API
            parkingRepository.getAudioNavigation(
                latitude = location.latitude,
                longitude = location.longitude,
                heading = heading,
                speed = speed
            ).fold(
                onSuccess = { response ->
                    handleAudioResponse(response)
                },
                onFailure = { error ->
                    // Log error but don't announce
                }
            )
        }
    }
    
    private fun handleAudioResponse(response: AudioNavigationResponse) {
        val currentTime = System.currentTimeMillis()
        
        // Check cooldown
        if (currentTime - lastAnnouncementTime < announcementCooldown) {
            return
        }
        
        // Process current announcement
        response.currentAnnouncement?.let { announcement ->
            if (announcement.text != null && response.shouldAnnounce) {
                announce(announcement.text, announcement.priority)
                lastAnnouncementTime = currentTime
            }
        }
        
        // Handle predictive announcements
        if (_audioState.value.predictiveEnabled) {
            response.predictiveAnnouncement?.let { prediction ->
                if (prediction.text != null && prediction.priority >= 3) {
                    // Queue predictive announcement
                    viewModelScope.launch {
                        kotlinx.coroutines.delay(2000) // Wait for main announcement
                        announce(prediction.text, prediction.priority)
                    }
                }
            }
        }
    }
    
    private fun announce(text: String, priority: Int) {
        if (!_audioState.value.isEnabled || _audioState.value.isSpeaking) return
        
        val utteranceId = UUID.randomUUID().toString()
        
        when (priority) {
            5, 4 -> {
                // High priority - interrupt current speech
                textToSpeech?.stop()
                textToSpeech?.speak(text, TextToSpeech.QUEUE_FLUSH, null, utteranceId)
            }
            else -> {
                // Normal priority - queue
                textToSpeech?.speak(text, TextToSpeech.QUEUE_ADD, null, utteranceId)
            }
        }
        
        _audioState.update { it.copy(
            lastAnnouncement = text,
            announcementHistory = (it.announcementHistory + text).takeLast(10)
        )}
    }
    
    fun toggleAudioNavigation() {
        _audioState.update { it.copy(isEnabled = !it.isEnabled) }
        
        if (_audioState.value.isEnabled) {
            announce("Audio navigation enabled", 2)
        }
    }
    
    fun togglePredictiveAnnouncements() {
        _audioState.update { it.copy(predictiveEnabled = !it.predictiveEnabled) }
    }
    
    fun setVolume(volume: Float) {
        _audioState.update { it.copy(volume = volume) }
        // Apply volume to TTS if supported
    }
    
    fun testAnnouncement() {
        announce(
            "Test announcement. Now on 42nd Street. Left side no parking. Right side metered parking available.",
            3
        )
    }
    
    override fun onCleared() {
        super.onCleared()
        textToSpeech?.stop()
        textToSpeech?.shutdown()
    }
}

data class AudioNavigationState(
    val isEnabled: Boolean = true,
    val isInitialized: Boolean = false,
    val isSpeaking: Boolean = false,
    val predictiveEnabled: Boolean = true,
    val volume: Float = 0.8f,
    val lastAnnouncement: String? = null,
    val announcementHistory: List<String> = emptyList()
)

data class AudioNavigationResponse(
    val currentAnnouncement: AudioAnnouncement?,
    val predictiveAnnouncement: AudioAnnouncement?,
    val shouldAnnounce: Boolean
)

data class AudioAnnouncement(
    val text: String?,
    val priority: Int,
    val category: String? = null
)