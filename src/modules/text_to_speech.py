import os
import tempfile
import threading
import time
import pyttsx3
import json
import logging

try:
    from google.cloud import texttospeech
    import pygame
    GOOGLE_TTS_AVAILABLE = True
except ImportError:
    GOOGLE_TTS_AVAILABLE = False

class TextToSpeech:
    def __init__(self):
        self.credentials_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'credentials.json'))
        self.use_google_tts = GOOGLE_TTS_AVAILABLE and os.path.exists(self.credentials_file)
        self.temp_files = []
        self.cleanup_lock = threading.Lock()
        
        if self.use_google_tts:
            logging.info("Using Google TTS")
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.credentials_file

            with open(self.credentials_file, 'r') as f:
                creds = json.load(f)

            os.environ['GOOGLE_CLOUD_QUOTA_PROJECT'] = creds.get('quota_project_id', '')

            self.client = texttospeech.TextToSpeechClient()
            self.voice = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name="en-US-Standard-D",
                ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
            )
            self.audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.0,
                pitch=0.0
            )
            pygame.mixer.init()
            self.cleanup_thread = threading.Thread(target=self._cleanup_files, daemon=True)
            self.cleanup_thread.start()
        else:
            logging.info("Using pyttsx3 TTS")
            self.engine = pyttsx3.init()
            voices = self.engine.getProperty('voices')
            female_voice = next((voice for voice in voices if "female" in voice.name.lower()), None)
            if female_voice:
                self.engine.setProperty('voice', female_voice.id)
            self.engine.setProperty('rate', 150)
            self.engine.setProperty('volume', 0.8)

    def speak(self, text):
        if self.use_google_tts:
            self._speak_google(text)
        else:
            self._speak_pyttsx3(text)

    def _speak_google(self, text):
        try:
            response = self.client.synthesize_speech(
                input=texttospeech.SynthesisInput(text=text),
                voice=self.voice,
                audio_config=self.audio_config
            )

            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio_file:
                temp_audio_file.write(response.audio_content)
                temp_audio_file_path = temp_audio_file.name

            pygame.mixer.music.load(temp_audio_file_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)

            with self.cleanup_lock:
                self.temp_files.append(temp_audio_file_path)

        except Exception as e:
            logging.error(f"Error in Google text-to-speech: {e}")

    def _speak_pyttsx3(self, text):
        self.engine.say(text)
        self.engine.runAndWait()

    def _cleanup_files(self):
        while True:
            with self.cleanup_lock:
                for file in self.temp_files[:]:
                    try:
                        os.unlink(file)
                        self.temp_files.remove(file)
                    except (PermissionError, FileNotFoundError):
                        pass
            time.sleep(5)

    def __del__(self):
        if hasattr(self, 'temp_files'):
            for file in self.temp_files:
                try:
                    os.unlink(file)
                except:
                    pass
