import os
import site
import pyaudio
import wave
import numpy as np
from contextlib import suppress
from openwakeword.model import Model

CHUNK_SIZE=1280

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
audio = pyaudio.PyAudio()

mic = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK_SIZE)

def install_models():
    src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
    dst_dir = os.path.join(site.getsitepackages()[0], 'openwakeword/resources')
    mod_dir = os.path.join(dst_dir, 'models')
    os.makedirs(dst_dir, exist_ok=True)
    with suppress(FileExistsError):
        os.symlink(os.path.join(src_dir, 'models'), mod_dir, target_is_directory=True)
    return mod_dir

dir = install_models()
model = Model(wakeword_models=[os.path.join(dir, 'hey_steve.onnx')], inference_framework='onnx', enable_speex_noise_suppression=True)

awake = False

if __name__ == "__main__":

    wf = wave.open('sounds/chirp.wav', 'rb')
    speaker = audio.open(format=audio.get_format_from_width(wf.getsampwidth()), channels=wf.getnchannels(), rate=wf.getframerate(), output=True)

    chirp = wf.readframes(wf.getnframes())
    #speaker.write(data)

    while True:
        # Get audio
        data = np.frombuffer(mic.read(CHUNK_SIZE, exception_on_overflow=False), dtype=np.int16)
        prediction = model.predict(data)

        for m in model.prediction_buffer.keys():
            scores = list(model.prediction_buffer[m])
            score = scores[-1]
            if score >= 0.2 and not awake:
                print(f'detected {score}')
                speaker.write(chirp)
                awake = True
            elif score < 0.2:
                awake = False

