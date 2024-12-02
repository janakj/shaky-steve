import os
import site
import pyaudio
import numpy as np
from contextlib import suppress
from openwakeword.model import Model
from steve.audio import audio, AudioClip
from steve.stt import SpeechToText


def install_models():
    src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
    dst_dir = os.path.join(site.getsitepackages()[0], 'openwakeword/resources')
    mod_dir = os.path.join(dst_dir, 'models')
    os.makedirs(dst_dir, exist_ok=True)
    with suppress(FileExistsError):
        os.symlink(os.path.join(src_dir, '..', 'models'), mod_dir, target_is_directory=True)
    return mod_dir


class WakeWord:
    CHUNK_SIZE = 1280
    FORMAT     = pyaudio.paInt16
    CHANNELS   = 1
    RATE       = 16000

    def __init__(self, model='hey_steve.onnx', threshold=0.5):
        self._model_dir = install_models()
        self._threshold = threshold
        self._model = Model(wakeword_models=[
            os.path.join(self._model_dir, model)],
            inference_framework='onnx',
            enable_speex_noise_suppression=True)

    def detect(self):
        self._model.reset()
        try:
            stream = audio.open(
                format=self.FORMAT, channels=self.CHANNELS, rate=self.RATE,
                frames_per_buffer=self.CHUNK_SIZE, input=True)

            while True:
                data = np.frombuffer(stream.read(self.CHUNK_SIZE, exception_on_overflow=False), dtype=np.int16)
                self._model.predict(data)

                for m in self._model.prediction_buffer.keys():
                    score = list(self._model.prediction_buffer[m])[-1]
                    if score >= self._threshold:
                        return score
        finally:
            stream.stop_stream()
            stream.close()


if __name__ == "__main__":
    detector = WakeWord()
    chirp = AudioClip('sounds/chirp.wav')
    stt_client = SpeechToText()

    while True:
        print('Listening for wake word')
        print(detector.detect())
        chirp.play()
        for value in stt_client.recognize():
            print(value)
            if value == 'stop':
                stt_client.stop()


