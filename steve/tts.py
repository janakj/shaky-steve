import google.api_core.exceptions
from google.cloud import texttospeech as tts
from queue import Queue
from threading import Thread
import itertools
import logging
from steve.audio import audio


log = logging.getLogger(__name__)


class TextToSpeech(Thread):
    def __init__(self, language='en-US', voice='en-US-Journey-D'):
        super().__init__()
        self._queue = Queue()
        self._client = tts.TextToSpeechClient()
        self._config = tts.StreamingSynthesizeConfig(voice=tts.VoiceSelectionParams(name=voice, language_code=language))
        self.daemon = True
        self.start()

    def run(self):
        self._stream = audio.open(format=audio.get_format_from_width(2), channels=1, rate=22050, output=True)
        try:
            def read_text():
                while True:
                    text = self._queue.get()
                    yield tts.StreamingSynthesizeRequest(input=tts.StreamingSynthesisInput(text=text))
                    self._queue.task_done()

            # Set the config for your stream. The first request must contain your
            # config, and then each subsequent request must contain text.
            cr = tts.StreamingSynthesizeRequest(streaming_config=self._config)

            while True:
                self._queue = Queue()

                gen = read_text()
                text = next(gen)

                try:
                    log.debug('Connecting to Google TTS')
                    responses = self._client.streaming_synthesize(itertools.chain([cr, text], gen))
                    for response in responses:
                        self._stream.write(response.audio_content)
                except google.api_core.exceptions.Aborted as e:
                    log.debug('Disconnected from Google TTS')
        finally:
            self._stream.stop_stream()
            self._stream.close()

    def say(self, text):
        self._queue.put(text)
