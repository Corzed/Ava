from ttkthemes import ThemedTk
from ai import AIAssistant
from gui import AIAssistantGUI


if __name__ == "__main__":
    root = ThemedTk(theme="equilux")
    ai_assistant = AIAssistant()
    app = AIAssistantGUI(root, ai_assistant)
    root.mainloop()