import openai
import time
from time import sleep
import os
import json
#from math import floor
#import code
from pydbus import SystemBus
from config import dbus_prefix
from threading import Thread
import logging
from gi.repository import GLib
from pydbus.generic import signal
#from queue import SimpleQueue, Empty
from dotenv import load_dotenv


# Path to the JSON file
functions_json_path = "functions.json"

def clear_json_file():
    with open(functions_json_path, "w") as f:
        json.dump({}, f)

# Load the JSON dictionary from the file if it exists, otherwise start with an empty dictionary
def load_functions():
    if os.path.exists(functions_json_path):
        with open(functions_json_path, "r") as f:
            content = f.read().strip()
            if content:
                return json.loads(content)
    return {}

# Save the JSON dictionary to the file
def save_functions(functions_dict):
    with open(functions_json_path, "w") as f:
        json.dump(functions_dict, f)

# Load previously defined functions from the JSON dictionary
def define_functions_from_json(functions_dict):
    for func_name, func_code in functions_dict.items():
        try:
            exec(func_code, env_variables)
        except NameError as e:
            #print(f"Failed to define {func_name}: {e}")
            pass


# Update the functions dictionary with the newly added functions
def update_functions_dict(new_names, response, functions_dict):
    for name in new_names:
        functions_dict[name] = response
    save_functions(functions_dict)

env_variables = globals()

# Load the functions dictionary
functions_dict = load_functions()

# Define previously added functions
define_functions_from_json(functions_dict)

log = logging.getLogger(__name__)

BUS_NAME = f'{dbus_prefix}.ChatGPT'

roboarm = None


#DBUS Class:

class DBusAPI(Thread):
    def __init__(self):
        super().__init__()
        self.dbus_loop = None
        self._active = False

    def run(self):
        log.debug(f'Publishing {BUS_NAME} on the system DBus bus')
        self.bus = SystemBus()
        self.bus.publish(BUS_NAME, self)
        self.dbus_loop = GLib.MainLoop()
        self.dbus_loop.run()

    def quit(self):
        log.debug('Quitting')
        if self.dbus_loop is not None:
            self.dbus_loop.quit()
        self.join()


    def move(self, text):
        #log.debug('Activating speech-to-text')
        #command_queue.put(True)
        response = generate_request(text)
        exec(response, globals())

    PropertiesChanged = signal()


DBusAPI.__doc__ = f'''
<node>
    <interface name='{BUS_NAME}'>
        <method name='move'>
            <arg type='s' name='text' direction='in'/>
        </method>
    </interface>
</node>
'''


def stop():
    print("Stopping servos.")
    roboarm.stop()

def off():
    print("Turning off.")
    roboarm.off()

def wrist_lr(value):
    print(f"Calling wrist_left_right with value: {value}.")
    roboarm.wrist_lr = str(value)

def torso(value):
    print(f"Calling torso with value: {value}.")
    roboarm.torso = str(value)

def wrist_ud(value):
    print(f"Calling wrist with: {value}.")
    roboarm.wrist_ud = str(value)

def elbow(value):
    print(f"Calling elbow with: {value}.")
    roboarm.elbow = str(value)

def shoulder(value):
    print(f"Calling shoulder with: {value}.")
    roboarm.shoulder = str(value)

def clamp(value):
    print(f"Calling clamp with: {value}.")
    roboarm.hand = str(value)

def reset():
    print("Setting robot to default position. ")
    roboarm.wakeup()

def power_down():
    print("Powering down robot. ")
    roboarm.sleep()
    roboarm.off()


def high_five():
    opts = {
        'block': GLib.Variant('b', False),
        'speed': GLib.Variant('d', 1.0)
    }

    torso = roboarm.torso
    shoulder = roboarm.shoulder
    elbow = roboarm.elbow
    wrist_ud = roboarm.wrist_ud
    wrist_lr = roboarm.wrist_lr
    hand = roboarm.hand

    roboarm.move('torso', '-0.429', opts)
    roboarm.move('shoulder', '18.799', opts)
    roboarm.move('elbow', '61.7', opts)
    roboarm.move('wrist_ud', '-5.632', opts)
    roboarm.move('wrist_lr', '0.282', opts)
    roboarm.move('hand', '0.03', opts)
    sleep(2)
    for i in range(5):
        roboarm.hand = '0'
        sleep(0.2)
        roboarm.hand = '0.03'
        sleep(0.2)

    roboarm.move('torso', torso, opts)
    roboarm.move('shoulder', shoulder, opts)
    roboarm.move('elbow', elbow, opts)
    roboarm.move('wrist_ud', wrist_ud, opts)
    roboarm.move('wrist_lr', wrist_lr, opts)
    roboarm.move('hand', hand, opts)

def point_up():
    roboarm.torso = "0"
    roboarm.wrist_ud = "0"
    roboarm.shoulder = "20"
    roboarm.elbow = "50"

"""
functions_dict = {
    "stop"     : stop,
    "off"      : off,
    "wrist_lr" : wrist_lr,
    "torso"    : torso,
    "wrist_ud" : wrist_ud,
    "elbow"    : elbow,
    "shoulder" : shoulder,
    "clamp"    : clamp,
    "reset"    : reset,
    "power_down": power_down,
    "high_five": high_five,
    "point_up": point_up
}
"""


"""
For prompt processing, you should ignore transcriptions that are not movement related. For example
, we can always prepend commands with "steve" and tell you to look for it.
Otherwise, you would try to turn arbitrary spoken language to movement commands which is not desired.
"""

###This is an alternative prompt version:

"""
You control a robotic arm with the following Python functions:

- `off()`: Turns off the robot.
- `torso(degree)`: Rotates the base from -90 to 90 degrees.
- `shoulder(degree)`: Moves the arm from -90 (back) to 90 (front).
- `elbow(degree)`: Extends (-58.4) or closes (61.7) the elbow.
- `wrist_lr(degree)`: Rotates the wrist horizontally from -90 to 90 degrees.
- `wrist_ud(degree)`: Rotates the wrist vertically from -90 (down) to 90 (up).
- `clamp(degree)`: Opens (0.03) or closes (0) the clamp.
- `reset()`: Resets the robot to the default position.
- `power_down()`: Powers down the robot and shuts off servos.
- `high_five()`: Makes the robot high five.
- `point_up()`: Points the robot arm upward.

You may encounter new functions such as `Alpha`. If you encounter such functions, you must execute them directly as they are defined in the environment.

Only execute commands prefixed with the keyword 'execute'.
Return only the Python code corresponding to the command, with no comments, explanations, or additional text.
"""

###

#The original prompt:

"""
You have the following Python functions that control servos in a robotic arm with six degrees of freedom.
The function off() turns the robot off.

The function torso(degree) rotates the robot's base from left(-90) to right(90).

The function shoulder(degree) moves the arm from back (-90) to front (90).
For shoulder: The value 0 points the arm up.

The function elbow(degree) extends (-58.4) or closes (61.7) the arm's elbow.
For elbow: The value 61.7 corresponds to the maximum extension, high point basically.

The function wrist_lr(degree) rotates the wrist horizontally from left (-90) to right(90).

The function wrist_ud(degree) rotates the wrist vertically from up (90) to down(-90).

The function clamp(degree) closes (0) or opens(0.03) the robot's clamp.
For function clamp: the passed value corresponds to the extent of opened clamp in meters.

The function reset() resets the bot to its default position.

The function power_down() powers the robot down to shut the servos off.

The function high_five() just makes the robot high five.

The function point_up() makes Steve look skyward.

Do not define the functions.

When the prompt includes the keyword 'execute', execute the corresponding Python function.

It is imperative that you only generate the code and no additional comments or any explanations, just the code. Literally just give me the code, nothing else.
Please provide only the Python code and no additional comments or explanations.
No comments at all, just the code; I don't want to see anything else.
Do not add '''python''' at the beginning of every code snippet, don't specify it at all.

"""

#

def generate_request(input_text):
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": """

You control a robotic arm with the following Python functions:

- `off()`: Turns off the robot.
- `torso(degree)`: Rotates the base from -90 to 90 degrees.
- `shoulder(degree)`: Moves the arm from -90 (back) to 90 (front).
- `elbow(degree)`: Extends (-58.4) or closes (61.7) the elbow.
- `wrist_lr(degree)`: Rotates the wrist horizontally from -90 to 90 degrees.
- `wrist_ud(degree)`: Rotates the wrist vertically from -90 (down) to 90 (up).
- `clamp(degree)`: Opens (0.03) or closes (0) the clamp.
- `reset()`: Resets the robot to the default position.
- `power_down()`: Powers down the robot and shuts off servos.
- `high_five()`: Makes the robot high five.
- `point_up()`: Points the robot arm upward.

You may encounter new functions such as `Alpha`. If you encounter such functions, you must execute them directly as they are defined in the environment.
Return only the Python code corresponding to the command, with no comments, explanations, or additional text.
"""},
            {"role": "user", "content": input_text}
        ]
    )
    #return response.choices[0].message['content']
    code = response.choices[0].message['content']
    code = code.strip()
    if code.startswith("```python"):
        code = code[10:]
    if code.endswith("```"):
        code = code[:-3]
    return code

def on_utterance(text):
    print(text)
    initial_keys = set(env_variables.keys())
    response = generate_request(text)
    print(response)
    exec(response, env_variables)
    new_names = find_new_names(initial_keys)
    if new_names:
        print(f"New functions added: {new_names}")
        update_functions_dict(new_names, response, functions_dict)
    else:
        print("No new functions were added.")
    print(env_variables.keys())

def find_new_names(initial_keys):
    current_keys = set(env_variables.keys())
    new_keys = current_keys - initial_keys
    return list(new_keys)


def main():
    #you can delete this function if you want to keep the previously defined functions in the code snippet
    clear_json_file()
    loop = GLib.MainLoop()
    loop.run()

    # print("\nType in '<<' to exit.\n")
    # while True:
    #     text = input("Type in something to do: ")
    #     if input == "<<":
    #         break
    #     start = time.time()
    #     response = generate_request(text)
    #     print(f"\nThe delay is: {floor(time.time() - start)} seconds.\n")
    #     print(response + '\n')


    # code.interact(local=globals())

if __name__ == "__main__":
    load_dotenv()

    openai.api_key = os.environ['OPENAI_API_KEY']

    bus = SystemBus()
    roboarm = bus.get(f'{dbus_prefix}.RoboArm')
    dbus_api = DBusAPI()
    stt = bus.get(f'{dbus_prefix}.SpeechToText')
    stt.onUtterance = on_utterance
    main()

#TODO: We want to have  JSON dictionary that records all of the newly added functions, the keys in this dictionary are the function names;
#the body is the string received from chatgpt that generated the code
#for each exec call it is updated if there is something new
#and each time we start the program we check the contents of the JSON file and define everything as done previously
"""
for example:
{
"move" : ... (ChatGPT generated code here)
}

"""
