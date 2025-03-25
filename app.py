import speech_recognition as sr
from gtts import gTTS
import pygame
import os
import re
import time
from threading import Thread, Event
import tempfile
import atexit

class VoiceBible:
    def __init__(self):
        # Audio setup
        pygame.mixer.init()
        self.stop_event = Event()
        self.current_speech_file = None
        self.temp_files = set()
        atexit.register(self.cleanup_temp_files)
        
        # Command processing
        self.current_verse = None
        self.is_playing = False
        self.loop_mode = False
        self.shuffle_mode = False
        self.speech_rate = 1.0
        self.active_mode = False  # Track if we're in command mode
        
        # Voice recognition
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 0.8
        self.wake_word = "bible"
        
        # Sample Bible data
        self.bible_data = {
            "john3:16": "For God so loved the world that he gave his one and only Son...",
            "psalm23:1": "The Lord is my shepherd, I lack nothing...",
            "genesis1:1": "In the beginning, God created the heavens and the earth..."
        }

    def cleanup_temp_files(self):
        """Clean up temp files with retries"""
        for file in list(self.temp_files):
            self._safe_remove(file)

    def _safe_remove(self, filepath):
        """Safely remove a file with retries"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            self.temp_files.discard(filepath)
        except:
            time.sleep(0.5)
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                self.temp_files.discard(filepath)
            except:
                pass

    def text_to_speech(self, text):
        """Convert text to speech"""
        tts = gTTS(text=text, lang='en', slow=False)
        temp_file = os.path.join(tempfile.gettempdir(), f"bible_{time.time()}.mp3")
        tts.save(temp_file)
        self.temp_files.add(temp_file)
        return temp_file

    def speak(self, text, interruptible=True):
        """Speak text with interrupt capability"""
        if interruptible and self.is_playing:
            self.stop_playback()
            time.sleep(0.3)
        
        speech_file = self.text_to_speech(text)
        self.current_speech_file = speech_file
        self.is_playing = True

        def play_audio():
            try:
                pygame.mixer.music.load(speech_file)
                pygame.mixer.music.play()
                
                while pygame.mixer.music.get_busy() and not self.stop_event.is_set():
                    time.sleep(0.1)
                
                if not self.stop_event.is_set():
                    Thread(target=self._safe_remove, args=(speech_file,), daemon=True).start()
            except Exception as e:
                print(f"Playback error: {e}")
            finally:
                self.is_playing = False
                self.stop_event.clear()

        Thread(target=play_audio, daemon=True).start()

    def stop_playback(self):
        """Stop current playback"""
        self.stop_event.set()
        pygame.mixer.music.stop()
        if self.current_speech_file:
            Thread(target=self._safe_remove, args=(self.current_speech_file,), daemon=True).start()
        self.is_playing = False

    def process_command(self, command):
        """Process a single command"""
        command = command.lower()
        
        # Common mishearings correction
        command = command.replace("jeans", "genesis")
        command = command.replace("sweet", "read")
        
        print(f"Processing command: {command}")
        
        if any(x in command for x in ["stop", "cancel", "quiet"]):
            self.stop_playback()
            self.speak("Playback stopped", interruptible=False)
            return True
            
        elif "read" in command:
            verse_ref = re.search(r"(?:read|play)\s+([\w\s:]+)", command)
            if verse_ref:
                verse = verse_ref.group(1).replace(" ", "").lower()
                if verse in self.bible_data:
                    self.current_verse = verse
                    self.speak(f"Reading {verse}. {self.bible_data[verse]}")
                    return True
                else:
                    self.speak("Verse not found", interruptible=False)
                    return False
                    
        elif "speed" in command:
            if "fast" in command:
                self.speech_rate = 1.5
                self.speak("Fast speed set", interruptible=False)
            elif "slow" in command:
                self.speech_rate = 0.75
                self.speak("Slow speed set", interruptible=False)
            else:
                self.speech_rate = 1.0
                self.speak("Normal speed set", interruptible=False)
            return True
            
        elif "loop" in command:
            self.loop_mode = not self.loop_mode
            status = "on" if self.loop_mode else "off"
            self.speak(f"Loop mode turned {status}", interruptible=False)
            return True
            
        self.speak("Command not understood", interruptible=False)
        return False

    def listen_for_commands(self):
        """Main listening loop with pause/resume capability"""
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source)
            paused = False  # Track pause state
            
            while True:
                try:
                    if paused:
                        # Special paused state - only responds to "Bible"
                        print("\n[Paused] Waiting for wake word...")
                        audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=2)
                        text = self.recognizer.recognize_google(audio).lower()
                        if self.wake_word in text:
                            paused = False
                            self.speak("Resuming playback", interruptible=False)
                            continue
                            
                    elif not self.active_mode:
                        # Normal sleep mode
                        print("\nSleep mode - say 'Bible' to activate")
                        audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=2)
                        text = self.recognizer.recognize_google(audio).lower()
                        if self.wake_word in text:
                            self.active_mode = True
                            self.speak("How can I help you?", interruptible=False)
                            
                    else:
                        # Active command mode
                        print("\nReady for commands (say 'pause' to pause)")
                        audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                        command = self.recognizer.recognize_google(audio).lower()
                        
                        if "pause" in command:
                            paused = True
                            self.stop_playback()
                            self.speak("Pausing playback", interruptible=False)
                        else:
                            self.process_command(command)
                            
                except sr.UnknownValueError:
                    if not paused:
                        self.speak("Please repeat that", interruptible=False)
                except sr.WaitTimeoutError:
                    if self.active_mode and not paused:
                        self.active_mode = False
                        self.speak("Returning to sleep", interruptible=False)
                except Exception as e:
                    print(f"System error: {e}")
                    time.sleep(1)

if __name__ == "__main__":
    app = VoiceBible()
    app.speak("Bible app ready. Say 'Bible' to activate.", interruptible=False)
    app.listen_for_commands()