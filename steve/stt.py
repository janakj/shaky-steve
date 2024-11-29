import math
import logging
import pyaudio
from threading import Event
from contextlib import suppress

import click
from google.protobuf.duration_pb2 import Duration  # protobuf
from pydbus.generic               import signal
from queue                        import Queue, Full, Empty
from steve.config                       import dbus_prefix
from google.cloud.speech          import (
    SpeechClient,
    RecognitionConfig,
    StreamingRecognitionConfig,
    StreamingRecognizeRequest,
    StreamingRecognizeResponse)

from steve.dbus import DBusAPI
from steve.utils import init_logging

BUS_NAME = f'{dbus_prefix}.SpeechToText'


DEFAULT_SAMPLE_RATE     = 16000   # The default audio sampling rate in Hz
DEFAULT_SAMPLE_WIDTH    = 2       # The default width of a single audio sample (1, 2, 3, or 4)
DEFAULT_CHANNELS        = 1       # The number of audio channels to use. Google STT defaults to 1
DEFAULT_CHUNK_DURATION  = 0.1     # The default chunk duration in seconds
DEFAULT_VAD_TIMEOUT     = 5       # Voice activity detection streaming timeout
DEFAULT_LANGUAGE        = 'en-US' # The language code to be used by the Google STT service


log = logging.getLogger(__name__)


class STTDBusAPI(DBusAPI):
    def __init__(self, on_activate=None):
        super().__init__(BUS_NAME)
        self._active = False
        self._voice_activity = False
        self.on_activate = on_activate

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, value):
        if self._active != value:
            self._active = value
            self.PropertiesChanged(BUS_NAME, {
                'active': self._active
            }, [])

    @property
    def voice_activity(self):
        return self._voice_activity

    @voice_activity.setter
    def voice_activity(self, value):
        if self._voice_activity != value:
            self._voice_activity = value
            self.PropertiesChanged(BUS_NAME, {
                'voice_activity': self._voice_activity
            }, [])

    def activate(self):
        if self.on_activate is not None:
            log.debug('Got DBus request to activate STT')
            self.on_activate(True)

    def deactivate(self):
        if self.on_activate is not None:
            log.debug('Got DBus request to deactivate STT')
            self.on_activate(False)

    def toggle(self):
        if self.on_activate is not None:
            log.debug('Got DBus request to toggle STT')
            self.on_activate(not self.active)

    Utterance = signal()


STTDBusAPI.__doc__ = f'''
<node>
    <interface name='{BUS_NAME}'>
        <method name='activate'></method>
        <method name='deactivate'></method>
        <method name='toggle'></method>
        <property name='active' type='b' access='read'>
            <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='true'/>
        </property>
        <property name='voice_activity' type='b' access='read'>
            <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='true'/>
        </property>
        <signal name="Utterance">
            <arg direction="out" name="text" type="s" />
        </signal>
    </interface>
</node>
'''


class BufferedAudioInput:
    def __init__(self, sample_rate, sample_width, channels, chunk_duration, max_queue_duration=1):
        self.sample_rate = sample_rate
        self.sample_width = sample_width
        self.channels = channels
        self.chunk_duration = chunk_duration
        self.stream = None

        log.debug(f'Using {pyaudio.get_portaudio_version_text()}')
        self.pyaudio = pyaudio.PyAudio()

        log.debug(f'Chunk duration is {chunk_duration} seconds')

        maxsize = round(max_queue_duration / chunk_duration)
        log.debug(f'Setting max audio queue size to {maxsize} chunks')
        self.queue = Queue(maxsize=maxsize)

    def __del__(self):
        if self.pyaudio is not None:
            with suppress(Exception): self.pyaudio.terminate()
            self.pyaudio = None

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
            log.warn('Audio queue overrun (STT too slow?)')
            self.flush()

        return None, pyaudio.paContinue

    def __enter__(self):
        self.flush()
        self.stream = self.pyaudio.open(
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


def start_streaming(mic: BufferedAudioInput, client: SpeechClient, config: StreamingRecognitionConfig):
    with mic as stream:
        try:
            dbus_api.active = True
            requests = (StreamingRecognizeRequest(audio_content=c) for c in stream)
            for response in client.streaming_recognize(config, requests):
                # Each response may contain multiple results, and each result may
                # contain multiple alternatives. Here we print only the
                # transcription for the top alternative of the top result.

                if response.speech_event_type == StreamingRecognizeResponse.SpeechEventType.SPEECH_ACTIVITY_BEGIN:
                    dbus_api.voice_activity = True
                elif response.speech_event_type == StreamingRecognizeResponse.SpeechEventType.SPEECH_ACTIVITY_END:
                    dbus_api.voice_activity = False
                elif response.speech_event_type == StreamingRecognizeResponse.SpeechEventType.SPEECH_ACTIVITY_TIMEOUT:
                    log.debug(f'Voice activity timeout')
                    return
                else:
                    if not response.results: continue
                    res = response.results[0]
                    if not res.alternatives: continue

                    t = res.alternatives[0].transcript.strip()
                    if len(t):
                        dbus_api.Utterance(t)
        finally:
            dbus_api.active = False
            dbus_api.voice_activity = False


@click.command()
@click.option('--verbose',         '-v', envvar='VERBOSE',         count=True,                                 help='Increase logging verbosity')
@click.option('--sample-rate',     '-r', envvar='SAMPLE_RATE',     type=int,   default=DEFAULT_SAMPLE_RATE,    help='Sample rate', show_default=True)
@click.option('--channels',        '-c', envvar='CHANNELS',        type=int,   default=DEFAULT_CHANNELS,       help='Number if channels', show_default=True)
@click.option('--chunk-duration',  '-d', envvar='CHUNK_DURATION',  type=float, default=DEFAULT_CHUNK_DURATION, help='Audio chunk duration in seconds', show_default=True)
@click.option('--vad-timeout',     '-t', envvar='VAD_TIMEOUT',     type=float, default=DEFAULT_VAD_TIMEOUT,    help='Voice activity detection timeout', show_default=True)
@click.option('--language',        '-l', envvar='LANGUAGE',        type=str,   default=DEFAULT_LANGUAGE,       help='Language for speech recognition', show_default=True)
def main(verbose, sample_rate, channels, chunk_duration, vad_timeout, language):
    global dbus_api

    init_logging(verbose)

    # The on_activate callback function is called from the thread used by the
    # DBus API.

    def on_activate(state):
        if state:
            # We have received a request to activate the STT service. Indicate
            # to the main thread to activate the streamer by setting the event's
            # internal flag to true.
            event.set()
        else:
            # Stop the ongoing streaming session (if any) by closing the
            # microphone input. This will indicate to the STT client to stop
            # streaming and the function start_streaming below will return.
            mic.stop_streaming()

    event = Event()
    dbus_api = STTDBusAPI(on_activate=on_activate)

    try:
        client = SpeechClient()

        rec_config = RecognitionConfig(
            language_code       = language,
            model               = 'latest_long',
            max_alternatives    = 1,
            use_enhanced        = True,
            sample_rate_hertz   = sample_rate,
            audio_channel_count = channels,
            encoding            = RecognitionConfig.AudioEncoding.LINEAR16)

        frac, seconds = math.modf(vad_timeout)
        timeout = Duration(seconds=round(seconds), nanos=round(frac * 10e8))

        config = StreamingRecognitionConfig(
            config                       = rec_config,
            interim_results              = False,
            enable_voice_activity_events = True,
            voice_activity_timeout       = StreamingRecognitionConfig.VoiceActivityTimeout(
                speech_start_timeout = timeout,
                speech_end_timeout   = timeout))

        mic = BufferedAudioInput(sample_rate, DEFAULT_SAMPLE_WIDTH, channels, chunk_duration)

        dbus_api.start()
        while True:
            event.clear()
            event.wait()
            log.debug('Starting streaming to Google STT')
            start_streaming(mic, client, config)
            log.debug('Streaming to Google STT stopped')

    finally:
        dbus_api.quit()


if __name__ == "__main__":
    main()
