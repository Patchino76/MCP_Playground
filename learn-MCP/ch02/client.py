# need to start a child process and send info to it via stdin

import subprocess
import json
import os

from utils import list_tools_message, initialize_message, initialized_message

# Start the child process
proc = subprocess.Popen(
    ['python', 'server.py'],  # Replace with your child script
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
    cwd=os.path.dirname(os.path.abspath(__file__))  # Set to directory containing client.py
)

message = 'hello\n'

def send_message(message):
    """Send a message to the child process."""
    print_response(message, prefix='[CLIENT]: ')
    proc.stdin.write(message)
    proc.stdin.flush()

def serialize_message(message):
    """Serialize a message to JSON format."""
    return json.dumps(message) + '\n'

def print_response(response, prefix = ""):
    """Print the response from the server."""
    try:
        parsed = json.loads(response)
        print(prefix,json.dumps(parsed, indent=2))
    except json.JSONDecodeError:
        print(prefix, response.strip())

def connect():
    print("Connecting to the server...")
    # 1. Ask for capabilities
    send_message(serialize_message(initialize_message))

    # Read response from child
    response = proc.stdout.readline()
    print_response(response, prefix='[SERVER]: \n')    

    # 2. Send initialized notification
    send_message(serialize_message(initialized_message))

def send_simple_message(message):
    # Send a simple text message to the child
    send_message(message)

    response = proc.stdout.readline()
    print_response(response, prefix='[SERVER]: \n')  

def list_tools():
    send_message(serialize_message(list_tools_message))
    # Read responses until we get a JSON response (not an error message)
    while True:
        response = proc.stdout.readline()
        print(f"Raw response: {repr(response)}")
        print_response(response, prefix='[SERVER]: \n')
        if response.strip() and response.strip().startswith('{"jsonrpc":'):
            return json.loads(response)['result']['tools']
        elif not response.strip():
            return []

def close_server():
    send_message('exit\n')

    exit_code = proc.wait()
    print(f"Child exited with code {exit_code}")

tools = []
def main():
    connect()
    tool_response = list_tools()
    tools.extend(tool_response)
    print(tools) 
    close_server()

main()
