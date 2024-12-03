import speech_recognition as sr
import threading
import time

class SpeechRecognizer:
    def __init__(self, wake_word="ava"):
        self.recognizer = sr.Recognizer()
        self.wake_word = wake_word.lower()
        self.is_listening = False
        self.callback = None
        self.listening_thread = None
        self.stop_listening_event = threading.Event()
        self.mode = 'wake_word'  # Modes: 'wake_word', 'command', 'answer'
        self.answer_timeout = 30  # 30-second timeout for answers

    def listen_in_background(self):
        if self.is_listening:
            print("Already listening.")
            return
        self.is_listening = True
        self.stop_listening_event.clear()
        self.mode = 'wake_word'
        self.listening_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listening_thread.start()

    def _listen_loop(self):
        while not self.stop_listening_event.is_set():
            print(f"Listening loop running in mode: {self.mode}")
            if self.mode == 'wake_word':
                with sr.Microphone() as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    self._listen_for_wake_word(source)
            elif self.mode == 'command':
                with sr.Microphone() as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    self._listen_for_command(source)
            elif self.mode == 'answer':
                with sr.Microphone() as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    self._listen_for_answer(source)
            time.sleep(0.1)

    def _listen_for_wake_word(self, source):
        try:
            print("Listening for wake word...")
            audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=25)
            text = self.recognizer.recognize_google(audio).lower()
            print(f"Heard: {text}")
            self._trigger_callback('partial_recognition', text=f"Heard: {text}")
            if self.wake_word in text:
                self.mode = 'command'
                self._trigger_callback('wake_word_detected')
        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            pass
        except sr.RequestError as e:
            print(f"Could not request results; {e}")
            self._trigger_callback('error', str(e))

    def _listen_for_command(self, source):
        print("Listening for command...")
        try:
            audio = self.recognizer.listen(source, timeout=15, phrase_time_limit=30)
            command_text = self.recognizer.recognize_google(audio)
            print(f"Recognized: {command_text}")
            self._trigger_callback('command_finished', text=command_text)
        except sr.WaitTimeoutError:
            print("No command detected.")
            self._trigger_callback('command_timeout')
        except sr.UnknownValueError:
            print("Could not understand the command.")
            self._trigger_callback('command_unrecognized')
        except sr.RequestError as e:
            print(f"Could not request results; {e}")
            self._trigger_callback('error', str(e))
        self.mode = 'wake_word'  # Return to wake word mode

    def _listen_for_answer(self, source):
        print("Listening for answer...")
        answer_text = ""
        start_time = time.time()
        try:
            while time.time() - start_time < self.answer_timeout:
                audio = self.recognizer.listen(source, timeout=15, phrase_time_limit=30)
                try:
                    text = self.recognizer.recognize_google(audio).lower()
                    print(f"Heard: {text}")
                    self._trigger_callback('partial_recognition', text=f"Heard: {text}")
                    if self.wake_word in text:
                        # User wants to cancel and issue a new command
                        self.mode = 'command'
                        self._trigger_callback('wake_word_detected')
                        return  # Break out to handle new command
                    else:
                        # Collect the user's answer
                        answer_text += " " + text
                        print(f"Answer collected: {answer_text.strip()}")
                        self._trigger_callback('answer_received', text=answer_text.strip())
                        self.mode = 'wake_word'  # After receiving the answer, return to wake word mode
                        return
                except sr.UnknownValueError:
                    pass  # Could not understand audio
        except sr.WaitTimeoutError:
            pass
        except sr.RequestError as e:
            print(f"Could not request results; {e}")
            self._trigger_callback('error', str(e))
        # If timeout occurs
        if time.time() - start_time >= self.answer_timeout:
            self._trigger_callback('answer_timeout')
            self.mode = 'wake_word'

    def start_listening_for_answer(self):
        print("Starting to listen for answer...")
        self.mode = 'answer'
        print(f"Mode set to {self.mode}")

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
