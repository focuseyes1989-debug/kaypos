# ui/ai_pages/ai_voice.py
"""
Voice Assistant for POS - Speech to Text
"""

import os
import threading
from typing import Optional, Callable
from loguru import logger

try:
    import speech_recognition as sr
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False
    logger.warning("SpeechRecognition not installed. Voice features disabled.")


class AIVoiceAssistant:
    """Voice recognition for POS"""
    
    def __init__(self):
        self._recognizer = None
        self._microphone = None
        self._is_listening = False
        self._callback = None
        
        if VOICE_AVAILABLE:
            self._recognizer = sr.Recognizer()
            try:
                self._microphone = sr.Microphone()
                # Adjust for ambient noise
                with self._microphone as source:
                    self._recognizer.adjust_for_ambient_noise(source, duration=1)
            except Exception as e:
                logger.warning(f"Microphone not available: {e}")
                self._microphone = None
    
    def is_available(self) -> bool:
        """Check if voice is available"""
        return VOICE_AVAILABLE and self._microphone is not None
    
    def listen_once(self, callback: Callable[[str, bool], None], timeout: int = 5):
        """
        Listen for voice once
        
        Args:
            callback: Function(transcribed_text, is_success)
            timeout: Maximum seconds to listen
        """
        if not self.is_available():
            callback("Voice feature not available. Please type your query.", False)
            return
        
        def listen_thread():
            try:
                with self._microphone as source:
                    logger.info("Listening...")
                    audio = self._recognizer.listen(source, timeout=timeout, phrase_time_limit=timeout)
                
                try:
                    text = self._recognizer.recognize_google(audio)
                    logger.info(f"Voice recognized: {text}")
                    callback(text, True)
                except sr.UnknownValueError:
                    callback("Sorry, I didn't catch that. Please speak clearly.", False)
                except sr.RequestError:
                    callback("Voice service error. Check your internet connection.", False)
                    
            except sr.WaitTimeoutError:
                callback("No voice detected. Please try again.", False)
            except Exception as e:
                logger.error(f"Voice error: {e}")
                callback(f"Error: {str(e)}", False)
        
        threading.Thread(target=listen_thread, daemon=True).start()
    
    def start_listening_continuous(self, callback: Callable[[str], None]):
        """Start continuous listening"""
        if not self.is_available():
            callback("Voice feature not available.")
            return
        
        self._is_listening = True
        self._callback = callback
        
        def continuous_thread():
            while self._is_listening:
                try:
                    with self._microphone as source:
                        audio = self._recognizer.listen(source, timeout=5, phrase_time_limit=3)
                    
                    try:
                        text = self._recognizer.recognize_google(audio)
                        if text.strip():
                            callback(text)
                    except (sr.UnknownValueError, sr.RequestError):
                        pass
                except sr.WaitTimeoutError:
                    pass
                except Exception as e:
                    logger.error(f"Continuous voice error: {e}")
        
        threading.Thread(target=continuous_thread, daemon=True).start()
    
    def stop_listening(self):
        """Stop continuous listening"""
        self._is_listening = False
    
    @staticmethod
    def get_voice_commands() -> dict:
        """Get available voice commands"""
        return {
            'search': ['search', 'find', 'ရှာဖွေ', 'ရှာ'],
            'add_to_cart': ['add', 'cart', 'ထည့်', 'ကတ်'],
            'remove': ['remove', 'delete', 'ဖျက်', 'ရှင်း'],
            'checkout': ['checkout', 'pay', 'ငွေရှင်း', 'ပေးချေ'],
            'cancel': ['cancel', 'stop', 'ပယ်ဖျက်', 'ရပ်'],
            'help': ['help', 'assist', 'အကူ', 'အညီ'],
        }