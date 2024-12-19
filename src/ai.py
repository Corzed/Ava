import json
import os
import platform
import psutil
import openai
from dotenv import load_dotenv
import glob
import re
import tempfile
import webbrowser
import time
import threading
import subprocess
from functools import lru_cache
from typing import Dict, Any, List
import pyautogui
import base64
import io

# Use Matplotlib's 'agg' backend to avoid GUI issues
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'config', '.env'))

class AIAssistant:
    def __init__(self, log_callback=None):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.model = os.getenv('OPENAI_MODEL')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in .env file")
        if not self.model:
            raise ValueError("OPENAI_MODEL not found in .env file")
        
        openai.api_key = self.api_key
        self.client = openai.OpenAI()
        self.assistant_id: str = None
        self.thread_id: str = None
        self.current_run_id: str = None
        self.log_messages: List[str] = []
        self.system_info = self.get_system_info()
        self.log_callback = log_callback  # Callback to send logs to GUI
    
    def log_to_terminal(self, message: str) -> None:
        """Send a message to the terminal via callback."""
        if self.log_callback:
            self.log_callback(message)
        else:
            self.log(f"Log (no callback): {message}")

    @lru_cache(maxsize=1)
    def get_system_info(self) -> Dict[str, Any]:
        try:
            info = {
                "os": platform.system(),
                "processor": platform.processor(),
                "architecture": platform.architecture()[0],
                "home_dir": os.path.expanduser("~"),
                "total_memory": psutil.virtual_memory().total,
                "available_memory": psutil.virtual_memory().available,
                "disk_usage": psutil.disk_usage('/'),
            }
            self.log(f"System information gathered: {json.dumps(info, indent=2)}")
            return info
        except Exception as e:
            self.log(f"Error gathering system information: {str(e)}")
            return {}

    def setup_assistant(self) -> None:
        try:
            system_info_str = json.dumps(self.system_info, indent=2)
            assistant = self.client.beta.assistants.create(
                name="Ava",
                instructions=f"""You are a voice-controlled AI assistant capable of performing actions on the local machine your name is Ava. 
                Provide concise and natural-sounding responses suitable for conversations. Do not include any formatting like the use of * in your response. You have access to the following system information:
                {system_info_str}
                Use this information to make informed decisions about file paths and system capabilities.""",
                model=self.model,
                tools=[
                    {"type": "function", "function": {
                    "name": "vision",
                    "description": "Captures the screen and analyzes it using the OpenAI Vision API. Can answer queries about specific elements or provide a general description.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "The question or task for analyzing the screen"}
                        },
                        "required": ["query"]
                    }
                }},
                    {"type": "function", "function": {
                        "name": "create_file",
                        "description": "Creates a new file on the local machine",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "filepath": {"type": "string", "description": "The full path of the file to create"}
                            },
                            "required": ["filepath"]
                        }
                    }},
                    {"type": "function", "function": {
                        "name": "edit_file",
                        "description": "Edits the contents of an existing file",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "filepath": {"type": "string", "description": "The full path of the file to edit"},
                                "content": {"type": "string", "description": "The new content to write to the file"}
                            },
                            "required": ["filepath", "content"]
                        }
                    }},
                    {"type": "function", "function": {
                        "name": "search_files",
                        "description": "Searches for files in the user's home directory",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "pattern": {"type": "string", "description": "The search pattern (e.g., '*.txt' for all text files)"},
                                "max_results": {"type": "integer", "description": "Maximum number of results to return"}
                            },
                            "required": ["pattern"]
                        }
                    }},
                    {"type": "function", "function": {
                        "name": "search_and_replace_in_files",
                        "description": "Searches for a pattern and replaces it in specified files",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "file_pattern": {"type": "string", "description": "The pattern to match files (e.g., '*.txt')"},
                                "search_pattern": {"type": "string", "description": "The pattern to search for in the files"},
                                "replacement": {"type": "string", "description": "The text to replace the matched pattern"},
                                "line_numbers": {"type": "array", "items": {"type": "integer"},
                                                 "description": "Optional: Specific line numbers to perform the replacement (empty for all lines)"}
                            },
                            "required": ["file_pattern", "search_pattern", "replacement"]
                        }
                    }},
                    {"type": "function", "function": {
                        "name": "generate_chart",
                        "description": "Generates a chart or graph based on provided data",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "chart_type": {"type": "string", "enum": ["line", "bar", "scatter", "pie"],
                                               "description": "The type of chart to generate"},
                                "data": {"type": "object", "description": "The data for the chart (format depends on chart type)"},
                                "title": {"type": "string", "description": "The title of the chart"}
                            },
                            "required": ["chart_type", "data", "title"]
                        }
                    }},
                    {"type": "function", "function": {
                        "name": "delete_file",
                        "description": "Deletes a file from the local machine",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "filepath": {"type": "string", "description": "The full path of the file to delete"}
                            },
                            "required": ["filepath"]
                        }
                    }},
                    {"type": "function", "function": {
                        "name": "execute_terminal_command",
                        "description": "Executes a terminal command on the local machine",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "command": {"type": "string", "description": "The terminal command to execute"}
                            },
                            "required": ["command"]
                        }
                    }},
                    {"type": "function", "function": {
                        "name": "read_highlighted_text",
                        "description": "Reads the text currently highlighted by the user",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }},
                    {"type": "function", "function": {
                        "name": "read_file",
                        "description": "Reads the contents of a file on the local machine",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "filepath": {"type": "string", "description": "The full path of the file to read"}
                            },
                            "required": ["filepath"]
                        }
                    }}
                ]
            )
            self.assistant_id = assistant.id
            self.log(f"Voice-enabled Assistant created with ID: {self.assistant_id}")
        except Exception as e:
            self.log(f"Error creating voice-enabled assistant: {str(e)}")
            raise

    def log(self, message: str) -> None:
        self.log_messages.append(message)
        print(message)

    def execute_tool(self, tool_name: str, arguments: str) -> str:
        if not tool_name:
            return "Error: Tool name is empty"

        args = json.loads(arguments)
        self.log(f"Executing tool: {tool_name}")
        self.log(f"Arguments: {args}")

        tool_functions = {
            "vision": lambda x: self.vision(x.get("query")),
            "create_file": self.create_file,
            "edit_file": self.edit_file,
            "search_files": self.search_files,
            "search_and_replace_in_files": self.search_and_replace_in_files,
            "generate_chart": self.generate_chart,
            "execute_terminal_command": self.execute_terminal_command,
            "read_file": self.read_file,
            "delete_file": self.delete_file,
            "read_highlighted_text": self.read_highlighted_text
        }

        if tool_name in tool_functions:
            return tool_functions[tool_name](args)
        else:
            error_message = f"Unknown tool: {tool_name}"
            self.log(error_message)
            return error_message

    def read_highlighted_text(self, args: Dict[str, Any]) -> str:
        try:
            import pyperclip
            import keyboard
            
            # Store the current clipboard content
            original_clipboard = pyperclip.paste()
            
            # Clear the clipboard
            pyperclip.copy('')
            
            # Simulate Ctrl+C to copy highlighted text
            keyboard.press_and_release('ctrl+c')
            time.sleep(0.1)  # Wait for the clipboard to be updated
            
            highlighted_text = pyperclip.paste()
            
            # Restore original clipboard content
            pyperclip.copy(original_clipboard)
            
            if highlighted_text:
                self.log(f"Read highlighted text: {highlighted_text}")
                return f"The highlighted text is: {highlighted_text}"
            else:
                return "No text was highlighted or copied. Please highlight some text and try again."
        except Exception as e:
            error_message = f"Error reading highlighted text: {str(e)}"
            self.log(error_message)
            return error_message

    def delete_file(self, args: Dict[str, Any]) -> str:
        filepath = args.get("filepath")
        if not filepath:
            return "Error: No filepath provided for delete_file"
        
        try:
            os.remove(filepath)
            self.log(f"File '{filepath}' has been deleted successfully.")
            return f"File '{filepath}' has been deleted successfully."
        except FileNotFoundError:
            error_message = f"Error: File '{filepath}' not found."
            self.log(error_message)
            return error_message
        except PermissionError:
            error_message = f"Error: Permission denied to delete file '{filepath}'."
            self.log(error_message)
            return error_message
        except Exception as e:
            error_message = f"Error deleting file: {str(e)}"
            self.log(error_message)
            return error_message
    
    def vision(self, query):
        """Captures the screen and analyzes it using the OpenAI Vision API."""
        try:
            # Capture the screen
            screenshot = pyautogui.screenshot()
        
            # Convert the screenshot to a base64-encoded string
            img_buffer = io.BytesIO()
            screenshot.save(img_buffer, format="PNG")
            img_buffer.seek(0)
            base64_image = base64.b64encode(img_buffer.read()).decode("utf-8")
            # Call the OpenAI Vision API with the base64 image
            response = openai.chat.completions.create(
                model="gpt-4o-mini",  # Replace with the desired model version
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": query},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}",
                                    "detail": "auto"  # Can be 'low', 'high', or 'auto' based on requirements
                                },
                            },
                        ],
                    }
                ],
            )
            
            # Extract and return the response content
            result = response.choices[0].message.content
            print("Vision tool output: " + result)
            return result

        except Exception as e:
            return f"Error analyzing screen: {e}"
        
    def read_file(self, args: Dict[str, Any]) -> str:
        filepath = args.get("filepath")
        if not filepath:
            return "Error: No filepath provided for read_file"
        
        try:
            with open(filepath, 'r') as file:
                content = file.read()
            self.log(f"File '{filepath}' has been read successfully.")
            return f"File contents:\n{content}"
        except Exception as e:
            error_message = f"Error reading file: {str(e)}"
            self.log(error_message)
            return error_message

    def execute_terminal_command(self, args: Dict[str, Any]) -> str:
        command = args.get("command")
        if not command:
            return "Error: No command provided for execute_terminal_command"

        def run_command():
            try:
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                self.log(f"Running command: {command}")

                # Read stdout and stderr line by line
                for line in iter(process.stdout.readline, ''):
                    self.log_to_terminal(f"OUTPUT: {line.strip()}")

                for line in iter(process.stderr.readline, ''):
                    self.log_to_terminal(f"ERROR: {line.strip()}")

                process.stdout.close()
                process.stderr.close()
                process.wait()

                if process.returncode == 0:
                    self.log_to_terminal(f"Command '{command}' completed successfully.")
                else:
                    self.log_to_terminal(f"Command failed with return code {process.returncode}.")
            except Exception as e:
                error_message = f"Error while running command: {e}"
                self.log_to_terminal(error_message)

        threading.Thread(target=run_command, daemon=True).start()
        return f"Command '{command}' is running. Check the terminal for logs."



    def create_file(self, args: Dict[str, Any]) -> str:
        filepath = args.get("filepath")
        if not filepath:
            return "Error: No filepath provided for create_file"
        
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w'):
                pass
            self.log(f"File '{filepath}' has been created successfully.")
            return f"File '{filepath}' has been created successfully."
        except Exception as e:
            error_message = f"Error creating file: {str(e)}"
            self.log(error_message)
            return error_message

    def edit_file(self, args: Dict[str, Any]) -> str:
        filepath = args.get("filepath")
        content = args.get("content")
        if not filepath or content is None:
            return "Error: Both filepath and content are required for edit_file"
        
        try:
            with open(filepath, 'w') as f:
                f.write(content)
            self.log(f"File '{filepath}' has been updated successfully.")
            return f"File '{filepath}' has been updated successfully."
        except Exception as e:
            error_message = f"Error editing file: {str(e)}"
            self.log(error_message)
            return error_message

    def search_files(self, args: Dict[str, Any]) -> str:
        pattern = args.get("pattern")
        max_results = args.get("max_results", 10)
        if not pattern:
            return "Error: No search pattern provided for search_files"
        
        try:
            home_dir = self.system_info['home_dir']
            search_path = os.path.join(home_dir, '**', pattern)
            results = glob.glob(search_path, recursive=True)[:max_results]
            
            if results:
                result_str = "\n".join(results)
                self.log(f"Found {len(results)} file(s):\n{result_str}")
                return f"Found {len(results)} file(s):\n{result_str}"
            else:
                return "No files found matching the pattern."
        except Exception as e:
            error_message = f"Error searching for files: {str(e)}"
            self.log(error_message)
            return error_message

    def search_and_replace_in_files(self, args: Dict[str, Any]) -> str:
        file_pattern = args.get("file_pattern")
        search_pattern = args.get("search_pattern")
        replacement = args.get("replacement")
        line_numbers = args.get("line_numbers", [])

        try:
            files = glob.glob(file_pattern, recursive=True)
            if not files:
                return f"No files found matching the pattern: {file_pattern}"

            total_replacements = 0
            for file_path in files:
                with open(file_path, 'r') as file:
                    lines = file.readlines()

                new_lines = []
                for i, line in enumerate(lines, 1):
                    if not line_numbers or i in line_numbers:
                        new_line, count = re.subn(search_pattern, replacement, line)
                        total_replacements += count
                    else:
                        new_line = line
                    new_lines.append(new_line)

                with open(file_path, 'w') as file:
                    file.writelines(new_lines)

            return f"Completed search and replace. Made {total_replacements} replacements across {len(files)} files."
        except Exception as e:
            return f"Error during search and replace: {str(e)}"

    def generate_chart(self, args: Dict[str, Any]) -> str:
        chart_type = args.get("chart_type", "bar")
        data = args.get("data", {"x": [1, 2, 3], "y": [4, 5, 6]})
        title = args.get("title", "Sample Chart")

        plt.figure(figsize=(10, 6))
        chart_functions = {
            "line": lambda: plt.plot(data.get("x", []), data.get("y", [])),
            "bar": lambda: plt.bar(data.get("x", []), data.get("y", [])),
            "scatter": lambda: plt.scatter(data.get("x", []), data.get("y", [])),
            "pie": lambda: plt.pie(data.get("values", []), labels=data.get("labels", []), autopct='%1.1f%%')
        }
        chart_functions.get(chart_type, chart_functions["bar"])()

        plt.title(title)
        plt.xlabel(data.get("xlabel", ""))
        plt.ylabel(data.get("ylabel", ""))

        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmpfile:
            plt.savefig(tmpfile.name)
            plt.close()

        webbrowser.open('file://' + tmpfile.name)
        threading.Thread(target=self.delete_file_after_closed, args=(tmpfile.name,), daemon=True).start()

        return f"Chart generated and opened in your default image viewer. The file will be deleted when you close the image."

    def delete_file_after_closed(self, filepath: str) -> None:
        initial_time = os.path.getmtime(filepath)
        while True:
            time.sleep(1)
            try:
                current_time = os.path.getmtime(filepath)
                if current_time != initial_time:
                    time.sleep(5)
                    os.remove(filepath)
                    self.log(f"Temporary chart file deleted: {filepath}")
                    break
            except FileNotFoundError:
                break

    def wait_for_run_completion(self) -> None:
        while True:
            run_status = self.client.beta.threads.runs.retrieve(
                thread_id=self.thread_id,
                run_id=self.current_run_id
            )
            if run_status.status in ["completed", "failed"]:
                break
            time.sleep(1)

    def get_ai_response(self, user_input: str) -> str:
        try:
            if not self.thread_id:
                thread = self.client.beta.threads.create()
                self.thread_id = thread.id
                self.log(f"New conversation thread created with ID: {self.thread_id}")

            if self.current_run_id:
                self.wait_for_run_completion()

            self.log(f"Sending user input to AI: {user_input}")
            self.client.beta.threads.messages.create(
                thread_id=self.thread_id,
                role="user",
                content=user_input
            )

            run = self.client.beta.threads.runs.create(
                thread_id=self.thread_id,
                assistant_id=self.assistant_id
            )
            self.current_run_id = run.id
            self.log(f"Created new run with ID: {run.id}")

            while True:
                run_status = self.client.beta.threads.runs.retrieve(
                    thread_id=self.thread_id,
                    run_id=run.id
                )
                self.log(f"Run status: {run_status.status}")
                
                if run_status.status == "completed":
                    messages = self.client.beta.threads.messages.list(thread_id=self.thread_id)
                    response = messages.data[0].content[0].text.value
                    self.log(f"AI response: {response}")
                    return response

                elif run_status.status == "requires_action":
                    tool_calls = run_status.required_action.submit_tool_outputs.tool_calls
                    tool_outputs = []

                    for tool_call in tool_calls:
                        function_name = tool_call.function.name
                        function_args = tool_call.function.arguments

                        self.log(f"Executing tool: {function_name}")
                        output = self.execute_tool(function_name, function_args)
                        tool_outputs.append({"tool_call_id": tool_call.id, "output": output})

                    self.log("Submitting tool outputs")
                    self.client.beta.threads.runs.submit_tool_outputs(
                        thread_id=self.thread_id,
                        run_id=run.id,
                        tool_outputs=tool_outputs
                    )

                elif run_status.status == "failed":
                    error_message = f"Run failed: {run_status.last_error.message}"
                    self.log(error_message)
                    return error_message

                time.sleep(1)  # Add a small delay to avoid excessive API calls

        except Exception as e:
            error_message = f"Error in get_ai_response: {str(e)}"
            self.log(error_message)
            return error_message

    def delete_assistant(self) -> None:
        if self.assistant_id:
            try:
                self.client.beta.assistants.delete(assistant_id=self.assistant_id)
                self.log(f"Assistant with ID {self.assistant_id} has been deleted.")
                self.assistant_id = None
            except Exception as e:
                self.log(f"Error deleting assistant: {str(e)}")

    def get_logs(self) -> str:
        return "\n".join(self.log_messages)
