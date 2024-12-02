import wave
import pyaudio
import logging
from contextlib import suppress
from queue import Queue, Full, Empty

audio = pyaudio.PyAudio()


log = logging.getLogger(__name__)


class AudioClip:
    def __init__(self,  filename):
        file = wave.open(filename, 'rb')

        self._width = file.getsampwidth()
        self._channels = file.getnchannels()
        self._rate = file.getframerate()

        self._data = file.readframes(file.getnframes())

    def play(self):
        stream = audio.open(format=audio.get_format_from_width(self._width), channels=self._channels, rate=self._rate, output=True)
        stream.write(self._data)
        stream.stop_stream()
        stream.close()


class BufferedAudioInput:
    def __init__(self, sample_rate, sample_width, channels, chunk_duration, max_queue_duration=1):
        self.sample_rate = sample_rate
        self.sample_width = sample_width
        self.channels = channels
        self.chunk_duration = chunk_duration
        self.stream = None

        log.debug(f'Using {pyaudio.get_portaudio_version_text()}')

        log.debug(f'Chunk duration is {chunk_duration} seconds')

        maxsize = round(max_queue_duration / chunk_duration)
        log.debug(f'Setting max audio queue size to {maxsize} chunks')
        self.queue = Queue(maxsize=maxsize)

    def flush(self):
        while True:
            try:
                self.queue.get(block=False)
            except Empty:
                break
            self.queue.task_done()

    def _enqueue(self, in_data, frame_count, time_info, status_flags):
        try:
            self.queue.put(in_data, block=False)
        except Full:
            log.warning('Audio queue overrun (STT too slow?)')
            self.flush()

        return None, pyaudio.paContinue

    def __enter__(self):
        self.flush()
        self.stream = audio.open(
            input             = True,
            rate              = self.sample_rate,
            format            = pyaudio.get_format_from_width(self.sample_width),
            channels          = self.channels,
            frames_per_buffer = round(self.sample_rate * self.chunk_duration),
            stream_callback   = self._enqueue)
        return self

    def stop_streaming(self):
        if self.stream is not None:
            with suppress(Exception): self.stream.stop_stream()
            with suppress(Exception): self.stream.close()
            self.stream = None
            self.queue.put(None)

    def __exit__(self, type, value, traceback):
        self.stop_streaming()

    def __iter__(self):
        while True:
            chunk = self.queue.get()
            self.queue.task_done()
            if chunk is None:
                return

            yield chunk

