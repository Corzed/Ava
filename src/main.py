from ttkthemes import ThemedTk
from ai import AIAssistant
from gui import AIAssistantGUI


if __name__ == "__main__":
    root = ThemedTk(theme="equilux")
    ai_assistant = AIAssistant(log_callback=lambda msg: app.add_terminal_message(msg))
    app = AIAssistantGUI(root, ai_assistant)
    root.mainloop()
