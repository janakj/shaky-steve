import os
import logging
from threading import Thread
from time import sleep
from openai import OpenAI
from pydbus import SystemBus
from steve.config import dbus_prefix
from gi.repository import GLib
from pydbus.generic import signal
from dotenv import load_dotenv


log = logging.getLogger(__name__)

# # Path to the JSON file
# functions_json_path = "functions.json"

# def clear_json_file():
#     with open(functions_json_path, "w") as f:
#         json.dump({}, f)

# Load the JSON dictionary from the file if it exists, otherwise start with an empty dictionary
# def load_functions():
#     if os.path.exists(functions_json_path):
#         with open(functions_json_path, "r") as f:
#             content = f.read().strip()
#             if content:
#                 return json.loads(content)
#     return {}

# Save the JSON dictionary to the file
# def save_functions(functions_dict):
#     with open(functions_json_path, "w") as f:
#         json.dump(functions_dict, f)

# Load previously defined functions from the JSON dictionary
# def define_functions_from_json(functions_dict):
#     for func_name, func_code in functions_dict.items():
#         try:
#             exec(func_code, env_variables)
#         except NameError as e:
#             #print(f"Failed to define {func_name}: {e}")
#             pass

# # Update the functions dictionary with the newly added functions
# def update_functions_dict(new_names, response, functions_dict):
#     for name in new_names:
#         functions_dict[name] = response
#     save_functions(functions_dict)

# env_variables = globals()

# Load the functions dictionary
# functions_dict = load_functions()

# Define previously added functions
# define_functions_from_json(functions_dict)


BUS_NAME = f'{dbus_prefix}.ChatGPT'

roboarm = None


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
        response = gpt.complete(text)
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
    roboarm.clamp = str(value)

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
    clamp = roboarm.clamp

    roboarm.move('torso', '-0.429', opts)
    roboarm.move('shoulder', '18.799', opts)
    roboarm.move('elbow', '61.7', opts)
    roboarm.move('wrist_ud', '-5.632', opts)
    roboarm.move('wrist_lr', '0.282', opts)
    roboarm.move('clamp', '0.03', opts)
    sleep(2)
    for i in range(5):
        roboarm.clamp = '0'
        sleep(0.2)
        roboarm.clamp = '0.03'
        sleep(0.2)

    roboarm.move('torso', torso, opts)
    roboarm.move('shoulder', shoulder, opts)
    roboarm.move('elbow', elbow, opts)
    roboarm.move('wrist_ud', wrist_ud, opts)
    roboarm.move('wrist_lr', wrist_lr, opts)
    roboarm.move('clamp', clamp, opts)

def point_up():
    roboarm.torso = "0"
    roboarm.wrist_ud = "0"
    roboarm.shoulder = "20"
    roboarm.elbow = "50"

# For prompt processing, you should ignore transcriptions that are not movement
# related. For example, we can always prepend commands with "steve" and tell you
# to look for it. Otherwise, you would try to turn arbitrary spoken language to
# movement commands which is not desired.

#### This is an alternative prompt version:

# You control a robotic arm with the following Python functions:
# - `off()`: Turns off the robot.
# - `torso(degree)`: Rotates the base from -90 to 90 degrees.
# - `shoulder(degree)`: Moves the arm from -90 (back) to 90 (front).
# - `elbow(degree)`: Extends (-58.4) or closes (61.7) the elbow.
# - `wrist_lr(degree)`: Rotates the wrist horizontally from -90 to 90 degrees.
# - `wrist_ud(degree)`: Rotates the wrist vertically from -90 (down) to 90 (up).
# - `clamp(degree)`: Opens (0.03) or closes (0) the clamp.
# - `reset()`: Resets the robot to the default position.
# - `power_down()`: Powers down the robot and shuts off servos.
# - `high_five()`: Makes the robot high five.
# - `point_up()`: Points the robot arm upward.
# You may encounter new functions such as `Alpha`. If you encounter such functions, you must execute them directly as they are defined in the environment.
# Only execute commands prefixed with the keyword 'execute'.
# Return only the Python code corresponding to the command, with no comments, explanations, or additional text.

####

#### he original prompt:

# You have the following Python functions that control servos in a robotic arm with six degrees of freedom.
# The function off() turns the robot off.

# The function torso(degree) rotates the robot's base from left(-90) to right(90).

# The function shoulder(degree) moves the arm from back (-90) to front (90).
# For shoulder: The value 0 points the arm up.

# The function elbow(degree) extends (-58.4) or closes (61.7) the arm's elbow.
# For elbow: The value 61.7 corresponds to the maximum extension, high point basically.

# The function wrist_lr(degree) rotates the wrist horizontally from left (-90) to right(90).

# The function wrist_ud(degree) rotates the wrist vertically from up (90) to down(-90).

# The function clamp(degree) closes (0) or opens(0.03) the robot's clamp.
# For function clamp: the passed value corresponds to the extent of opened clamp in meters.

# The function reset() resets the bot to its default position.

# The function power_down() powers the robot down to shut the servos off.

# The function high_five() just makes the robot high five.

# The function point_up() makes Steve look skyward.

# Do not define the functions.

# When the prompt includes the keyword 'execute', execute the corresponding Python function.

# It is imperative that you only generate the code and no additional comments or any explanations, just the code. Literally just give me the code, nothing else.
# Please provide only the Python code and no additional comments or explanations.
# No comments at all, just the code; I don't want to see anything else.
# Do not add '''python''' at the beginning of every code snippet, don't specify it at all.

####

class ChatGPT:
    def __init__(self, api_key=os.environ['OPENAI_API_KEY'], model='gpt-4o'):
        self._model = model
        self._client = OpenAI(api_key=api_key)

    def respond(self, text):
        stream = self._client.chat.completions.create(
            model=self._model,
            stream=True,
            messages=[{
                "role"    : "system",
                "content" : """
Respond as a goofy voice-controlled robot.
Do not use emojis.
Generate short responses.
"""
            }, {
                "role"    : "user",
                "content" : text
            }]
        )

        text = ''
        for chunk in stream:
            yield chunk.choices[0].delta.content or ""

    def program(self, text):
        stream = self._client.chat.completions.create(
            model=self._model,
            stream=True,
            messages=[{
                "role"    : "system",
                "content" : """
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

Return only the Python code corresponding to the command, with no comments, explanations, or additional text.
"""
            }, {
                "role"    : "user",
                "content" : text
            }]
        )

        text = ''
        for chunk in stream:
            text += chunk.choices[0].delta.content or ""

        text = text.strip()
        if text.startswith("```python"):
            text = text[10:-4]
        return text


def main():
    loop = GLib.MainLoop()
    loop.run()
    # code.interact(local=globals())


if __name__ == "__main__":
    load_dotenv()

    gpt = ChatGPT()

    bus = SystemBus()
    roboarm = bus.get(f'{dbus_prefix}.RoboArm')
    dbus_api = DBusAPI()
    stt = bus.get(f'{dbus_prefix}.SpeechToText')
    #stt.onUtterance = on_utterance
    main()
