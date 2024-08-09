import queue
import re
import sys
import time
import logging
import pyaudio

from google.cloud import speech
from threading import Thread
from pydbus import SystemBus
from gi.repository import GLib
from pydbus.generic import signal
from queue import SimpleQueue, Empty
from config import dbus_prefix

# dbus_api.Utterance(text) --> send the call with DBUS
# dbus_api.active = True --> for controlling the LED
# dbus_api.active = False --> for controlling the LED

# How to restart the service:
# sudo systemctl restart steve-led
# sudo systemctl restart steve-navigator


# Audio recording parameters
STREAMING_LIMIT = 240000  # 4 minutes
SAMPLE_RATE = 16000
CHUNK_SIZE = int(SAMPLE_RATE / 10)  # 100ms

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"

# Separate Constants:

log = logging.getLogger(__name__)

BUS_NAME = f'{dbus_prefix}.SpeechToText'

command_queue = SimpleQueue()

#Silence Threshold is: 5 seconds --> print loop
"""
def generate_revised_content(content):
    response = openai.completions.create(
        model="davinci",  # Your desired model
        prompt=content,
        max_tokens=30000,  # Extended for longer responses
        temperature=0.5,  # Adjust for creativity
        top_p=1,  # Control response diversity
        frequency_penalty=0,  # Fine-tune word frequency
        presence_penalty=0  # Fine-tune word presence
    )
    return response.choices[0].text
"""
# DBUS CLASS:


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

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, value):
        if self._active != value:
            self.PropertiesChanged(BUS_NAME, {
                'active': self._active
            }, [])
        self._active = value

    def activate(self):
        log.debug('Activating speech-to-text')
        command_queue.put(True)

    def deactivate(self):
        log.debug('Deactivating speech-to-text')
        command_queue.put(False)

    PropertiesChanged = signal()
    Utterance = signal()


DBusAPI.__doc__ = f'''
<node>
    <interface name='{BUS_NAME}'>
        <method name='activate'></method>
        <method name='deactivate'></method>
        <property name='active' type='b' access='read'>
            <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='true'/>
        </property>
        <signal name="Utterance">
            <arg direction="out" name="text" type="s" />
        </signal>
    </interface>
</node>
'''


def get_current_time() -> int:
    """Return Current Time in MS.

    Returns:
        int: Current Time in MS.
    """

    return int(round(time.time() * 1000))


class ResumableMicrophoneStream:
    """Opens a recording stream as a generator yielding the audio chunks."""

    def __init__(
        self: object,
        rate: int,
        chunk_size: int,
    ) -> None:
        """Creates a resumable microphone stream.

        Args:
        self: The class instance.
        rate: The audio file's sampling rate.
        chunk_size: The audio file's chunk size.

        returns: None
        """
        self._rate = rate
        self.chunk_size = chunk_size
        self._num_channels = 1
        self._buff = queue.Queue()
        self.closed = True
        self.start_time = get_current_time()
        self.restart_counter = 0
        self.audio_input = []
        self.last_audio_input = []
        self.result_end_time = 0
        self.is_final_end_time = 0
        self.final_request_end_time = 0
        self.bridging_offset = 0
        self.last_transcript_was_final = False
        self.new_stream = True
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            channels=self._num_channels,
            rate=self._rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )

    def __enter__(self: object) -> object:
        """Opens the stream.

        Args:
        self: The class instance.

        returns: None
        """
        self.closed = False
        return self

    def __exit__(
        self: object,
        type: object,
        value: object,
        traceback: object,
    ) -> object:
        """Closes the stream and releases resources.

        Args:
        self: The class instance.
        type: The exception type.
        value: The exception value.
        traceback: The exception traceback.

        returns: None
        """
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

    def deactivate(self):
        """Deactivates the stream and releases resources."""
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(
        self: object,
        in_data: object,
        *args: object,
        **kwargs: object,
    ) -> object:
        """Continuously collect data from the audio stream, into the buffer.

        Args:
        self: The class instance.
        in_data: The audio data as a bytes object.
        args: Additional arguments.
        kwargs: Additional arguments.

        returns: None
        """
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self: object) -> object:
        """Stream Audio from microphone to API and to local buffer

        Args:
            self: The class instance.

        returns:
            The data from the audio stream.
        """
        while not self.closed:
            data = []

            if self.new_stream and self.last_audio_input:
                chunk_time = STREAMING_LIMIT / len(self.last_audio_input)

                if chunk_time != 0:
                    if self.bridging_offset < 0:
                        self.bridging_offset = 0

                    if self.bridging_offset > self.final_request_end_time:
                        self.bridging_offset = self.final_request_end_time

                    chunks_from_ms = round(
                        (self.final_request_end_time - self.bridging_offset)
                        / chunk_time
                    )

                    self.bridging_offset = round(
                        (len(self.last_audio_input) - chunks_from_ms) * chunk_time
                    )

                    for i in range(chunks_from_ms, len(self.last_audio_input)):
                        data.append(self.last_audio_input[i])

                self.new_stream = False

            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            self.audio_input.append(chunk)

            if chunk is None:
                return
            data.append(chunk)
            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)

                    if chunk is None:
                        return
                    data.append(chunk)
                    self.audio_input.append(chunk)

                except queue.Empty:
                    break

            yield b"".join(data)


def listen_print_loop(responses: object, stream: object, command_q) -> None:
    """Iterates through server responses and prints them.

    The responses passed is a generator that will block until a response
    is provided by the server.

    Each response may contain multiple results, and each result may contain
    multiple alternatives. Here we
    print only the transcription for the top alternative of the top result.

    In this case, responses are provided for interim results as well. If the
    response is an interim one, print a line feed at the end of it, to allow
    the next result to overwrite it, until the response is a final one. For the
    final one, print a newline to preserve the finalized transcription.

    Arg:
        responses: The responses returned from the API.
        stream: The audio stream to be processed.
    """
    last_print_time = time.time()
    #if current time - most recent printed word >= time limit: quit, just stream.deactivate()
    for response in responses:
        try:
            val = command_q.get(block=False)
            if val == False:
                stream.deactivate()
                return
        except Empty:
            pass
        if time.time() - last_print_time >= 5:
            sys.stdout.write("Closing mic since it has been longer than 5 seconds of silence.\n")
            stream.deactivate()
            return  
        #if get_current_time() - stream.start_time > STREAMING_LIMIT:
            #stream.start_time = get_current_time()
            #break

        if not response.results:
            continue

        result = response.results[0]

        if not result.alternatives:
            continue

        transcript = result.alternatives[0].transcript

        result_seconds = 0
        result_micros = 0

        if result.result_end_time.seconds:
            result_seconds = result.result_end_time.seconds

        if result.result_end_time.microseconds:
            result_micros = result.result_end_time.microseconds

        stream.result_end_time = int((result_seconds * 1000) + (result_micros / 1000))

        corrected_time = (
            stream.result_end_time
            - stream.bridging_offset
            + (STREAMING_LIMIT * stream.restart_counter)
        )
        # Display interim results, but with a carriage return at the end of the
        # line, so subsequent lines will overwrite them.

        if result.is_final:
            sys.stdout.write(GREEN)
            sys.stdout.write("\033[K")
            sys.stdout.write(str(corrected_time) + ": " + transcript + "\n")

            stream.is_final_end_time = stream.result_end_time
            stream.last_transcript_was_final = True
            last_print_time = time.time()
            dbus_api.Utterance(transcript)

            # Exit recognition if any of the transcribed phrases could be
            # one of our keywords.
            # if re.search(r"\b(exit|quit)\b", transcript, re.I):
                # sys.stdout.write(YELLOW)
                # sys.stdout.write("Exiting...\n")
                # stream.closed = True
                # break
        else:
            sys.stdout.write(RED)
            sys.stdout.write("\033[K")
            sys.stdout.write(str(corrected_time) + ": " + transcript + "\r")

            stream.last_transcript_was_final = False
            last_print_time = time.time()
        


def main(command_q) -> None:
    """Start bidirectional streaming from microphone input to speech API"""
    client = speech.SpeechClient()
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=SAMPLE_RATE,
        language_code="en-US",
        max_alternatives=1,
    )

    streaming_config = speech.StreamingRecognitionConfig(
        config=config, interim_results=True
    )

    mic_manager = ResumableMicrophoneStream(SAMPLE_RATE, CHUNK_SIZE)
    #dbus_api.active = True
    print(mic_manager.chunk_size)
    sys.stdout.write(YELLOW)
    sys.stdout.write('\nListening. \n\n')
    sys.stdout.write("End (ms)       Transcript Results/Status\n")
    sys.stdout.write("=====================================================\n")

    with mic_manager as stream:
        dbus_api.active = False
        try:
            while not stream.closed:
                sys.stdout.write(YELLOW)
                sys.stdout.write(
                    "\n" + str(STREAMING_LIMIT * stream.restart_counter) + ": NEW REQUEST\n"
                )

                stream.audio_input = []
                audio_generator = stream.generator()

                requests = (
                    speech.StreamingRecognizeRequest(audio_content=content)
                    for content in audio_generator
                )

                responses = client.streaming_recognize(streaming_config, requests)

                # Now, put the transcription responses to use.
                listen_print_loop(responses, stream, command_q)
                if stream.result_end_time > 0:
                    stream.final_request_end_time = stream.is_final_end_time
                stream.result_end_time = 0
                stream.last_audio_input = []
                stream.last_audio_input = stream.audio_input
                stream.audio_input = []
                stream.restart_counter = stream.restart_counter + 1

                if not stream.last_transcript_was_final:
                    sys.stdout.write("\n")
                
                stream.new_stream = True
            
        finally:
            dbus_api.active = True
            stream.deactivate()  # Ensure the stream is deactivated if the loop exits normally


def run(verbose):
    global dbus_api
    if verbose == 0:
        level = logging.WARNING
    if verbose == 1:
        level = logging.INFO
    if verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level)

    dbus_api = DBusAPI()
    try:
        dbus_api.start()
        try:
            while True:
                activate = command_queue.get()
                if activate:
                    # Call main here
                    main(command_queue)
        except KeyboardInterrupt:
            pass
            #sys.exit() can be added but is not necessary
    finally:
        dbus_api.quit()


if __name__ == "__main__":
    run(2)
    #verbosity level can be changed as preferred, 2 is a good baseline
