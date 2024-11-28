import google.api_core.exceptions
import pyaudio
from google.cloud import texttospeech as tts
from queue import Queue
from threading import Thread
import itertools

queue = Queue()


def tts_client():
    global queue

    client = tts.TextToSpeechClient()
    config = tts.StreamingSynthesizeConfig(voice=tts.VoiceSelectionParams(name="en-US-Journey-D", language_code="en-US"))

    def read_text():
        while True:
            text = queue.get()
            yield tts.StreamingSynthesizeRequest(input=tts.StreamingSynthesisInput(text=text))
            queue.task_done()

    # Set the config for your stream. The first request must contain your
    # config, and then each subsequent request must contain text.
    cr = tts.StreamingSynthesizeRequest(streaming_config=config)

    while True:
        queue = Queue()

        gen = read_text()
        text = next(gen)

        try:
            print('Connecting to Google TTS')
            responses = client.streaming_synthesize(itertools.chain([cr, text], gen))
            for response in responses:
                stream.write(response.audio_content)
        except google.api_core.exceptions.Aborted as e:
            print('Disconnected from Google TTS')


def say(text):
    queue.put(text)


if __name__ == "__main__":

    # Open the audio interface for output
    audio = pyaudio.PyAudio()
    stream = audio.open(format=audio.get_format_from_width(2), channels=1, rate=22050, output=True)

    # Create a Google TTS streaming client

    client = Thread(target=tts_client)
    client.daemon = True
    client.start()

    # Read text from the user and write it to the client. Make sure to end the
    # text with a punctuation mark to get an immediate response.
    try:
        while True:
            text = input('Text: ')
            say(text)
    except KeyboardInterrupt:
        pass
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()