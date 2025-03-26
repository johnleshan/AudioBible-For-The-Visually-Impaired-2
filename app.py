import speech_recognition as sr
from gtts import gTTS
import pygame
import os
import re
import time
import tempfile
from threading import Thread, Event
import queue

class AdvancedVoiceBible:
    def __init__(self):
        # Audio engine setup
        pygame.mixer.init()
        self.audio_queue = queue.Queue()
        self.playback_event = Event()
        self.playback_event.set()  # Start with playback enabled
        
        # Voice recognition
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 1.0  # Longer pauses between phrases
        self.wake_words = {"bible", "scripture", "word"}
        
        # App states
        self.states = {
            "SLEEP": 0,
            "ACTIVE": 1,
            "PAUSED": 2
        }
        self.current_state = self.states["SLEEP"]
        
        # Audio settings
        self.speech_rate = 1.0  # Normal speed
        self.volume = 0.7       # Default volume
        
        # Initialize components
        self._init_audio_worker()
        self._load_bible_data()
        
    def _init_audio_worker(self):
        """Background thread for smooth audio playback"""
        def audio_worker():
            while True:
                audio_file = self.audio_queue.get()
                if audio_file == "STOP":
                    break
                    
                pygame.mixer.music.load(audio_file)
                pygame.mixer.music.set_volume(self.volume)
                pygame.mixer.music.play()
                
                # Wait for playback to complete or interruption
                while pygame.mixer.music.get_busy():
                    if not self.playback_event.is_set():
                        pygame.mixer.music.pause()
                        self.playback_event.wait()  # Wait for resume
                        pygame.mixer.music.unpause()
                    time.sleep(0.1)
                
                # Clean up file after playback
                self._safe_remove(audio_file)
        
        Thread(target=audio_worker, daemon=True).start()
    
    def _load_bible_data(self):
        """Load Bible verses (replace with your actual data source)"""
        self.bible_data = {
            "genesis1:1": "In the beginning, God created the heavens and the earth...",
            "john3:16": "For God so loved the world that he gave his only Son...",
            "psalm23:1": "The Lord is my shepherd, I shall not want..."
        }
    
    def speak(self, text, interruptible=True, priority=False):
        """Convert text to speech and queue for playback"""
        if interruptible and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            
        tts = gTTS(text=text, lang='en', slow=False)
        temp_file = os.path.join(tempfile.gettempdir(), f"bible_{time.time()}.mp3")
        tts.save(temp_file)
        
        if priority:
            # Clear queue for high-priority messages
            while not self.audio_queue.empty():
                old_file = self.audio_queue.get()
                self._safe_remove(old_file)
        
        self.audio_queue.put(temp_file)
    
    def _safe_remove(self, filepath):
        """Safely remove audio files with retries"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except:
            time.sleep(0.5)
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except:
                pass
    
    def process_command(self, command):
        """Execute recognized commands with proper feedback"""
        print(f"Executing command: {command}")
        
        # Clean and normalize the command
        command = command.lower().strip()
        command = command.replace(" first", " fast")  # Common mishearing fix
        
        # State management commands
        if "pause" in command:
            self.current_state = self.states["PAUSED"]
            self.playback_event.clear()
            self.speak("Playback paused", interruptible=True)
            return True
            
        if any(word in command for word in {"resume", "continue"}):
            self.current_state = self.states["ACTIVE"]
            self.playback_event.set()
            self.speak("Resuming playback", interruptible=True)
            return True
            
        if any(word in command for word in {"sleep", "stop listening"}):
            self.current_state = self.states["SLEEP"]
            self.speak("Going to sleep", interruptible=True)
            return True
        
        # Audio control commands
        if any(word in command for word in {"faster", "speed up"}):
            self.speech_rate = min(2.0, self.speech_rate + 0.25)
            self.speak(f"Speed set to {self.speech_rate}x", interruptible=True)
            return True
            
        if any(word in command for word in {"slower", "slow down"}):
            self.speech_rate = max(0.5, self.speech_rate - 0.25)
            self.speak(f"Speed set to {self.speech_rate}x", interruptible=True)
            return True
        
        # Verse reading commands
        verse_match = re.search(r"(?:read|say|play)\s+([\w\s:]+)", command)
        if verse_match:
            verse_ref = verse_match.group(1).replace(" ", "").lower()
            if verse_ref in self.bible_data:
                self.speak(f"Reading {verse_ref}. {self.bible_data[verse_ref]}", interruptible=True)
                return True
            else:
                self.speak("Verse not found", interruptible=True)
                return False
        
        # No valid command found
        self.speak("Command not recognized", interruptible=True)
        return False

    def listen_loop(self):
        """Main listening loop with guaranteed command execution"""
        print("Voice Bible System Ready")
        self.speak("Application ready. Say 'Bible' to begin.", interruptible=False)
        
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
            
            while True:
                try:
                    state_name = list(self.states.keys())[self.current_state]
                    print(f"\nCurrent state: {state_name}")
                    
                    # SLEEP STATE
                    if self.current_state == self.states["SLEEP"]:
                        try:
                            print("Listening for wake word...")
                            audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=2)
                            text = self.recognizer.recognize_google(audio).lower()
                            print(f"Heard: {text}")
                            
                            if any(word in text for word in self.wake_words):
                                self.current_state = self.states["ACTIVE"]
                                self.speak("How can I help you?", interruptible=True)
                        
                        except (sr.WaitTimeoutError, sr.UnknownValueError):
                            continue
                    
                    # ACTIVE STATE
                    elif self.current_state == self.states["ACTIVE"]:
                        try:
                            print("Waiting for command...")
                            audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                            command = self.recognizer.recognize_google(audio).lower()
                            print(f"Command: {command}")
                            
                            # Process the command
                            if not self.process_command(command):
                                self.speak("Please try again", interruptible=True)
                        
                        except sr.WaitTimeoutError:
                            self.current_state = self.states["SLEEP"]
                            self.speak("Returning to sleep", interruptible=True)
                        except sr.UnknownValueError:
                            self.speak("I didn't understand that", interruptible=True)
                    
                    # PAUSED STATE
                    elif self.current_state == self.states["PAUSED"]:
                        try:
                            print("Paused - waiting for resume...")
                            audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=2)
                            text = self.recognizer.recognize_google(audio).lower()
                            
                            if any(word in text for word in {"resume", "continue"} | self.wake_words):
                                self.current_state = self.states["ACTIVE"]
                                self.playback_event.set()
                                self.speak("Resuming playback", interruptible=True)
                        
                        except sr.UnknownValueError:
                            continue
                
                except Exception as e:
                    print(f"System error: {e}")
                    self.current_state = self.states["SLEEP"]
                    time.sleep(1)

if __name__ == "__main__":
    app = AdvancedVoiceBible()
    app.speak("Bible application ready", interruptible=False)
    app.listen_loop()