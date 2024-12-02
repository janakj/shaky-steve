from dotenv import load_dotenv
load_dotenv()

from steve.color   import RGB, RGBA, HSL, PQT, color as color_names, scale, dim
from steve.audio   import AudioClip
from steve.stt     import SpeechToText
from steve.wake    import WakeWord
from steve.tts     import TextToSpeech
from steve.jupyter import LEDs, Servos
from steve.chatgpt import ChatGPT

try:
    from steve.mouse import Mouse
except OSError:
    pass