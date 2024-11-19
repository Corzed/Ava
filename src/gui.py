import tkinter as tk
from tkinter import scrolledtext, ttk
import threading
import queue
import time
from modules.speech_recognizer import SpeechRecognizer
from modules.text_to_speech import TextToSpeech

class AIAssistantGUI:
    def __init__(self, master, ai_assistant):
        self.master = master
        self.master.title("Advanced Virtual Assistant")
        self.master.geometry("1000x700")
        self.master.configure(bg='#2C2F33')

        self.style = ttk.Style(self.master)
        self.style.theme_use("equilux")

        self.ai_assistant = ai_assistant
        self.speech_recognizer = SpeechRecognizer(wake_word="ava")
        self.speech_recognizer.set_callback(self.speech_recognizer_callback)
        self.text_to_speech = TextToSpeech()

        self.listening_enabled = False

        self.terminal_queue = queue.Queue()
        self.create_widgets()

        # Setup assistant after creating widgets
        self.setup_assistant()

        # Start the terminal update loop
        self.update_terminal()

        # Bind the window closing event
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        main_frame = ttk.Frame(self.master, style='TFrame')
        main_frame.pack(expand=True, fill='both', padx=10, pady=10)

        # Chat display
        chat_frame = ttk.Frame(main_frame, style='TFrame')
        chat_frame.pack(side=tk.LEFT, expand=True, fill='both', padx=(0, 5))

        self.chat_display = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, bg='#36393F', fg='white', font=('Helvetica', 10))
        self.chat_display.pack(expand=True, fill='both', padx=5, pady=5)
        self.chat_display.config(state=tk.DISABLED)

        # Input area
        input_frame = ttk.Frame(chat_frame, style='TFrame')
        input_frame.pack(fill='x', padx=5, pady=5)

        self.text_input = ttk.Entry(input_frame, font=('Helvetica', 10))
        self.text_input.pack(side=tk.LEFT, expand=True, fill='x', padx=(0, 5))
        self.text_input.bind("<Return>", self.send_text_input)

        send_button = ttk.Button(input_frame, text="Send", command=self.send_text_input, style='Accent.TButton')
        send_button.pack(side=tk.RIGHT)

        # Terminal and controls
        right_frame = ttk.Frame(main_frame, style='TFrame')
        right_frame.pack(side=tk.RIGHT, expand=True, fill='both', padx=(5, 0))

        # Terminal
        self.terminal = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, bg='#000000', fg='#00FF00', font=('Courier', 9))
        self.terminal.pack(expand=True, fill='both', padx=5, pady=5)
        self.terminal.config(state=tk.DISABLED)

        # Controls
        control_frame = ttk.Frame(right_frame, style='TFrame')
        control_frame.pack(fill='x', padx=5, pady=5)

        self.status_label = ttk.Label(control_frame, text="Voice recognition is off", style='TLabel')
        self.status_label.pack(side=tk.LEFT, pady=5)

        self.toggle_button = ttk.Button(control_frame, text="Enable Listening", command=self.toggle_listening, style='Accent.TButton')
        self.toggle_button.pack(side=tk.RIGHT, padx=(10, 0))

    def setup_assistant(self):
        def setup():
            self.ai_assistant.setup_assistant()
            self.master.after(0, self.add_terminal_message, "System: AI Assistant setup completed.")
            self.master.after(0, self.text_to_speech.speak, "I am ready. Enable listening or type to get started!")

        threading.Thread(target=setup, daemon=True).start()
        self.add_terminal_message("System: Setting up AI Assistant...")

    def toggle_listening(self):
        self.listening_enabled = not self.listening_enabled
        if self.listening_enabled:
            self.toggle_button.config(text="Disable Listening")
            self.status_label.config(text="Voice recognition is on")
            self.speech_recognizer.listen_in_background()
            self.add_terminal_message("System: Voice recognition enabled.")
        else:
            self.toggle_button.config(text="Enable Listening")
            self.status_label.config(text="Voice recognition is off")
            self.speech_recognizer.stop_listening()
            self.add_terminal_message("System: Voice recognition disabled.")

    def speech_recognizer_callback(self, event, text=None):
        print(f"speech_recognizer_callback received event: {event}, text: {text}")
        if event == 'wake_word_detected':
            self.master.after(0, self.wake_word_detected)
        elif event == 'command_finished':
            self.master.after(0, self.command_received, text)
        elif event == 'command_timeout':
            self.master.after(0, self.command_received)
        elif event == 'command_unrecognized':
            self.master.after(0, self.command_received)
        elif event == 'partial_recognition':
            self.master.after(0, self.add_terminal_message, text)
        elif event == 'error':
            self.master.after(0, self.add_terminal_message, f"Error: {text}")
        elif event == 'answer_received':
            self.master.after(0, self.answer_received, text)
        elif event == 'answer_timeout':
            self.master.after(0, self.answer_timeout)

    def wake_word_detected(self):
        self.status_label.config(text="Wake word detected! Processing command...")
        self.add_terminal_message("System: Wake word 'Ava' detected.")
        self.text_to_speech.speak("Listening")

    def command_received(self, command):
        if command:
            self.add_terminal_message(f"Command recognized: {command}")
            self.process_input(command)
        else:
            self.status_label.config(text="Say 'Ava' to wake me up!")
            self.add_terminal_message("System: No command detected.")
            self.text_to_speech.speak("I didn't catch that. Please try again.")

    def send_text_input(self, event=None):
        user_input = self.text_input.get()
        if user_input:
            self.text_input.delete(0, tk.END)
            self.process_input(user_input)

    def process_input(self, user_input):
        self.add_message(f"You: {user_input}", "white")
        self.add_terminal_message(f"User: {user_input}")
        self.status_label.config(text="Processing your request...")

        def get_response():
            response = self.ai_assistant.get_ai_response(user_input)
            self.master.after(0, self.display_and_speak_response, response)

        threading.Thread(target=get_response, daemon=True).start()

    def display_and_speak_response(self, response):
        self.add_message(f"AI: {response}", "light green")
        self.add_terminal_message(f"AI: {response}")
        self.status_label.config(text="Speaking...")

        def speak():
            self.text_to_speech.speak(response)
            # After speaking, check if the response is a question
            if response.strip().endswith("?"):
                self.master.after(0, self.start_listening_for_answer)
            else:
                self.master.after(0, self.status_label.config, {"text": "Ready for next input"})

        threading.Thread(target=speak, daemon=True).start()

    def add_message(self, message, color):
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, message + "\n\n")
        # Apply color to the latest message
        self.chat_display.tag_add(color, "end-2l", "end-1c")
        self.chat_display.tag_config(color, foreground=color)
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    def add_terminal_message(self, message):
        self.terminal_queue.put(message)

    def update_terminal(self):
        while not self.terminal_queue.empty():
            message = self.terminal_queue.get()
            self.terminal.config(state=tk.NORMAL)
            self.terminal.insert(tk.END, message + "\n")
            self.terminal.config(state=tk.DISABLED)
            self.terminal.see(tk.END)
        self.master.after(100, self.update_terminal)


    def on_closing(self):
        self.add_terminal_message("System: Deleting AI Assistant...")
        self.listening_enabled = False
        self.speech_recognizer.stop_listening()

        def cleanup():
            self.ai_assistant.delete_assistant()
            self.add_terminal_message("System: AI Assistant deleted. Closing application.")
            self.text_to_speech.speak("Goodbye!")
            time.sleep(1)
            self.master.after(0, self.master.destroy)

        threading.Thread(target=cleanup, daemon=True).start()

    def start_listening_for_answer(self):
        self.add_terminal_message("System: Response is a question. Starting to listen for answer.")
        self.status_label.config(text="Waiting for your answer...")
        self.speech_recognizer.start_listening_for_answer()

    def answer_received(self, answer):
        print(f"answer_received called with answer: {answer}")
        try:
            self.add_terminal_message(f"Answer received: {answer}")
            self.add_message(f"You: {answer}", "white")
            self.status_label.config(text="Processing your answer...")
            # No need to stop listening here as the recognizer handles mode switching

            def process_answer():
                try:
                    response = self.ai_assistant.get_ai_response(answer)
                    self.master.after(0, self.display_and_speak_response, response)
                except Exception as e:
                    print(f"Exception in process_answer: {e}")
                    self.add_terminal_message(f"Error processing answer: {e}")

            threading.Thread(target=process_answer, daemon=True).start()
        except Exception as e:
            print(f"Exception in answer_received: {e}")
            self.add_terminal_message(f"Error in answer_received: {e}")

    def answer_timeout(self):
        self.add_terminal_message("System: Answer timeout. Returning to wake word detection.")
        self.text_to_speech.speak("Time out. Please say 'Ava' to ask a new question.")
        self.status_label.config(text="Say 'Ava' to wake me up!")
