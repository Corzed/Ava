import speech_recognition as sr
import threading
import time
import webrtcvad
import io
import wave


class SpeechRecognizer:
    def __init__(self, wake_word="ava"):
        self.recognizer = sr.Recognizer()
        self.wake_word = wake_word.lower()
        self.is_listening = False
        self.callback = None
        self.listening_thread = None
        self.stop_listening_event = threading.Event()
        self.use_wake_word = True
        self.mode = 'wake_word'  # Modes: 'wake_word', 'command', 'answer', 'continuous_command'
        self.answer_timeout = 30
        self.lock = threading.Lock()  # Added to ensure thread-safe access

    def listen_in_background(self):
        with self.lock:  # Ensure thread-safe access
            if self.is_listening:
                print("Already listening.")
                return

            self.is_listening = True
            self.stop_listening_event.clear()
            self.mode = 'wake_word' if self.use_wake_word else 'continuous_command'
            self.listening_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.listening_thread.start()

    def _configure_microphone(self):
        try:
            return sr.Microphone()
        except OSError as e:
            print(f"Error configuring microphone: {e}")
            raise

    def _listen_loop(self):
        try:
            with self._configure_microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

                while not self.stop_listening_event.is_set():
                    print(f"Listening loop running in mode: {self.mode}")

                    try:
                        if self.mode == 'wake_word':
                            self._listen_for_wake_word(source)
                        elif self.mode == 'command':
                            self._listen_for_command(source)
                        elif self.mode == 'answer':
                            self._listen_for_answer(source)
                        elif self.mode == 'continuous_command':
                            self._listen_for_continuous_command(source)
                    except sr.RequestError as e:
                        print(f"Request error in listen loop: {e}")
                    except OSError as e:
                        if "Stream closed" in str(e):
                            print("Audio stream closed. Restarting loop.")
                            break
                        else:
                            print(f"Unexpected OSError: {e}")
                    except Exception as e:
                        print(f"Unexpected error in listen loop: {e}")

                    time.sleep(0.1)
        except OSError as e:
            print(f"Error in _listen_loop setup: {e}")
            self.stop_listening_event.set()  # Ensure the loop exits cleanly
        except Exception as e:
            print(f"General error in _listen_loop setup: {e}")
            self.stop_listening_event.set()

    def _listen_for_wake_word(self, source):
        try:
            print("Listening for wake word...")
            audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)
            if self._preprocess_audio(audio.get_wav_data()):
                text = self.recognizer.recognize_google(audio).lower()
                print(f"Heard: {text}")

                if self.wake_word in text:
                    command_part = text.split(self.wake_word, 1)[1].strip()
                    if command_part:
                        self._trigger_callback('command_finished', text=command_part)
                    else:
                        self.mode = 'command'
                        self._trigger_callback('wake_word_detected')
        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            pass
        except sr.RequestError as e:
            self._trigger_callback('error', str(e))

    def _listen_for_command(self, source):
        print("Listening for command...")
        try:
            audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
            if self._preprocess_audio(audio.get_wav_data()):
                command_text = self.recognizer.recognize_google(audio)
                print(f"Recognized: {command_text}")
                self._trigger_callback('command_finished', text=command_text)
        except sr.WaitTimeoutError:
            self._trigger_callback('command_timeout', text="No command detected.")
        except sr.UnknownValueError:
            self._trigger_callback('command_unrecognized', text="Could not understand the command.")
        except sr.RequestError as e:
            self._trigger_callback('error', str(e))
        finally:
            if self.use_wake_word:
                self.mode = 'wake_word'

    def _listen_for_answer(self, source):
        print("Listening for answer...")
        try:
            audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
            if self._preprocess_audio(audio.get_wav_data()):
                answer_text = self.recognizer.recognize_google(audio).lower()
                if answer_text.strip():
                    print(f"Answer recognized: {answer_text}")
                    self._trigger_callback('answer_received', text=answer_text)
                    self.mode = 'wake_word' if self.use_wake_word else 'continuous_command'
        except sr.UnknownValueError:
            print("Could not understand the answer.")
            self._trigger_callback('answer_timeout')
        except sr.RequestError as e:
            self._trigger_callback('error', str(e))
        if self.use_wake_word:
            self.mode = 'wake_word'

    def _listen_for_continuous_command(self, source):
        print("Listening for continuous command...")
        while not self.stop_listening_event.is_set():
            try:
                audio = self.recognizer.listen(source, phrase_time_limit=10)
                if self._preprocess_audio(audio.get_wav_data()):
                    command_text = self.recognizer.recognize_google(audio)
                    print(f"Recognized: {command_text}")
                    self._trigger_callback('command_finished', text=command_text)
            except sr.UnknownValueError:
                print("Could not understand the command.")
            except sr.RequestError as e:
                self._trigger_callback('error', str(e))

    def start_listening_for_answer(self):
        if self.use_wake_word:
            print("Starting to listen for answer...")
            self.mode = 'answer'

    def stop_listening(self):
        self.stop_listening_event.set()
        if self.listening_thread and self.listening_thread.is_alive():
            self.listening_thread.join()
        self.is_listening = False

    def set_callback(self, callback):
        self.callback = callback

    def _trigger_callback(self, event, text=None):
        print(f"_trigger_callback called with event: {event}, text: {text}")
        if self.callback:
            self.callback(event, text)

    def _preprocess_audio(self, audio_data, sample_rate=16000):
        """Filters out non-speech audio using VAD."""
        vad = webrtcvad.Vad(2)  # 0-3 (0: least aggressive, 3: most aggressive)
        raw_audio = io.BytesIO(audio_data)
        with wave.open(raw_audio) as wf:
            audio = wf.readframes(wf.getnframes())
        frame_duration = 30  # ms
        frame_length = int(sample_rate * frame_duration / 1000) * 2
        speech_frames = [audio[i:i+frame_length] for i in range(0, len(audio), frame_length)]
        return any(vad.is_speech(frame, sample_rate) for frame in speech_frames)
