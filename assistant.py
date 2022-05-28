#!/usr/bin/env python3
import json
import uuid
import os.path
import logging
import asyncio
import concurrent.futures
from threading import Thread
from pydbus.generic import signal
from queue import Queue

import grpc
import google.auth.transport.requests
import google.auth.transport.grpc
import google.oauth2.credentials
from google.assistant.embedded.v1alpha2 import embedded_assistant_pb2, embedded_assistant_pb2_grpc
from tenacity import retry, stop_after_attempt, retry_if_exception

from googlesamples.assistant.grpc import assistant_helpers
from googlesamples.assistant.grpc import audio_helpers
from googlesamples.assistant.grpc import device_helpers

from gi.repository import GLib
from pydbus import SystemBus
from config import dbus_prefix, verbose, assistant_api_endpoint, project_id, device_id, device_model_id

bus = SystemBus()
roboarm = bus.get(f'{dbus_prefix}.RoboArm')
asyncio_loop = asyncio.get_event_loop()

api = None

queue = Queue()

END_OF_UTTERANCE = embedded_assistant_pb2.AssistResponse.END_OF_UTTERANCE
DIALOG_FOLLOW_ON = embedded_assistant_pb2.DialogStateOut.DIALOG_FOLLOW_ON
CLOSE_MICROPHONE = embedded_assistant_pb2.DialogStateOut.CLOSE_MICROPHONE
PLAYING = embedded_assistant_pb2.ScreenOutConfig.PLAYING


class Assistant(object):
    def __init__(self, language_code, device_model_id, device_id,
                 conversation_stream, display,
                 channel, deadline_sec, device_handler):
        self.language_code = language_code
        self.device_model_id = device_model_id
        self.device_id = device_id
        self.conversation_stream = conversation_stream
        self.display = display

        # Opaque blob provided in AssistResponse that,
        # when provided in a follow-up AssistRequest,
        # gives the Assistant a context marker within the current state
        # of the multi-Assist()-RPC "conversation".
        # This value, along with MicrophoneMode, supports a more natural
        # "conversation" with the Assistant.
        self.conversation_state = None
        # Force reset of first conversation.
        self.is_new_conversation = True

        # Create Google Assistant API gRPC client.
        self.assistant = embedded_assistant_pb2_grpc.EmbeddedAssistantStub(channel)
        self.deadline = deadline_sec

        self.device_handler = device_handler

    def __enter__(self):
        return self

    def __exit__(self, etype, e, traceback):
        if e:
            return False
        self.conversation_stream.close()

    def is_grpc_error_unavailable(e):
        is_grpc_error = isinstance(e, grpc.RpcError)
        if is_grpc_error and (e.code() == grpc.StatusCode.UNAVAILABLE):
            logging.error('grpc unavailable error: %s', e)
            return True
        return False

    @retry(reraise=True, stop=stop_after_attempt(3),
           retry=retry_if_exception(is_grpc_error_unavailable))
    def assist(self):
        """Send a voice request to the Assistant and playback the response.

        Returns: True if conversation should continue.
        """
        continue_conversation = False
        device_actions_futures = []
        ended = False

        self.conversation_stream.start_recording()
        logging.info('Recording audio request.')

        def iter_log_assist_requests():
            for c in self.gen_assist_requests():
                assistant_helpers.log_assist_request_without_audio(c)
                yield c
            logging.debug('Reached end of AssistRequest iteration.')

        # This generator yields AssistResponse proto messages
        # received from the gRPC Google Assistant API.
        for resp in self.assistant.Assist(iter_log_assist_requests(),
                                          self.deadline):
            assistant_helpers.log_assist_response_without_audio(resp)
            if resp.event_type == END_OF_UTTERANCE:
                logging.info('End of audio request detected.')
                logging.info('Stopping recording.')
                ended = True
                self.conversation_stream.stop_recording()
            if resp.speech_results:
                text = ' '.join(r.transcript for r in resp.speech_results)
                logging.info('Transcript of user request: "%s".' % text)
                if ended == True:
                    print(f"text: {text}")
                    api.SpeechToText(text)
            if len(resp.audio_out.audio_data) > 0:
                if not self.conversation_stream.playing:
                    self.conversation_stream.stop_recording()
                    self.conversation_stream.start_playback()
                    logging.info('Playing assistant response.')
                self.conversation_stream.write(resp.audio_out.audio_data)
            if resp.dialog_state_out.conversation_state:
                conversation_state = resp.dialog_state_out.conversation_state
                logging.debug('Updating conversation state.')
                self.conversation_state = conversation_state
            if resp.dialog_state_out.volume_percentage != 0:
                volume_percentage = resp.dialog_state_out.volume_percentage
                logging.info('Setting volume to %s%%', volume_percentage)
                self.conversation_stream.volume_percentage = volume_percentage
            if resp.dialog_state_out.microphone_mode == DIALOG_FOLLOW_ON:
                continue_conversation = True
                logging.info('Expecting follow-on query from user.')
            elif resp.dialog_state_out.microphone_mode == CLOSE_MICROPHONE:
                continue_conversation = False
            if resp.device_action.device_request_json:
                device_request = json.loads(
                    resp.device_action.device_request_json
                )
                fs = self.device_handler(device_request)
                if fs:
                    device_actions_futures.extend(fs)
            # if self.display and resp.screen_out.data:
            #     system_browser = browser_helpers.system_browser
            #     system_browser.display(resp.screen_out.data)

        if len(device_actions_futures):
            logging.info('Waiting for device executions to complete.')
            concurrent.futures.wait(device_actions_futures)

        logging.info('Finished playing assistant response.')
        self.conversation_stream.stop_playback()
        return continue_conversation

    def gen_assist_requests(self):
        """Yields: AssistRequest messages to send to the API."""

        config = embedded_assistant_pb2.AssistConfig(
            audio_in_config=embedded_assistant_pb2.AudioInConfig(
                encoding='LINEAR16',
                sample_rate_hertz=self.conversation_stream.sample_rate,
            ),
            audio_out_config=embedded_assistant_pb2.AudioOutConfig(
                encoding='LINEAR16',
                sample_rate_hertz=self.conversation_stream.sample_rate,
                volume_percentage=self.conversation_stream.volume_percentage,
            ),
            dialog_state_in=embedded_assistant_pb2.DialogStateIn(
                language_code=self.language_code,
                conversation_state=self.conversation_state,
                is_new_conversation=self.is_new_conversation,
            ),
            device_config=embedded_assistant_pb2.DeviceConfig(
                device_id=self.device_id,
                device_model_id=self.device_model_id,
            )
        )
        if self.display:
            config.screen_out_config.screen_mode = PLAYING
        # Continue current conversation with later requests.
        self.is_new_conversation = False
        # The first AssistRequest must contain the AssistConfig
        # and no audio data.
        yield embedded_assistant_pb2.AssistRequest(config=config)
        for data in self.conversation_stream:
            # Subsequent requests need audio data, but not config.
            yield embedded_assistant_pb2.AssistRequest(audio_in=data)


class DBusAPI(Thread):
    def __init__(self):
        super().__init__()
        self.dbus_loop = None
        self._active = False

    def run(self):
        bus.publish(f'{dbus_prefix}.Assistant', self)

        self.dbus_loop = GLib.MainLoop()
        self.dbus_loop.run()

    def quit(self):
        if self.dbus_loop is not None:
            self.dbus_loop.quit()

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, value):
        self._active = value
        self.PropertiesChanged(f'{dbus_prefix}.Assistant', {
            'active': self._active
        }, [])

    def activate(self):
        queue.put_nowait(True)

    def _invoke_coro(self, coro):
        f = asyncio.run_coroutine_threadsafe(coro, asyncio_loop)
        return f.result()

    PropertiesChanged = signal()
    SpeechToText = signal()



DBusAPI.__doc__ = f'''
<node>
    <interface name='{dbus_prefix}.Assistant'>
        <method name='activate'></method>
        <property name='active' type='b' access='read'>
            <annotation name='org.freedesktop.DBus.Property.EmitsChangedSignal' value='true'/>
        </property>
        <signal name="SpeechToText">
            <arg direction="out" name="text" type="s" />
        </signal>
    </interface>
</node>
'''


def load_credentials(filename='/srv/assistant/credentials.json'):
    # Load OAuth 2.0 credentials.
    try:
        with open(filename, 'r') as f:
            credentials = google.oauth2.credentials.Credentials(token=None, **json.load(f))
            http_request = google.auth.transport.requests.Request()
            credentials.refresh(http_request)
            return (credentials, http_request)
    except Exception as e:
        logging.error('Error loading credentials: %s', e)
        logging.error('Run google-oauthlib-tool to initialize new OAuth 2.0 credentials.')
        raise e


def run_assistant(api, credentials, http_request, model_id, device_id):
    # Create an authorized gRPC channel.
    grpc_channel = google.auth.transport.grpc.secure_authorized_channel(credentials, http_request, assistant_api_endpoint)
    logging.info(f'Connecting to {assistant_api_endpoint}')

    # Configure audio source and sink.
    audio_device = audio_helpers.SoundDeviceStream(sample_rate=16000, sample_width=2, block_size=6400, flush_size=25600)

    # Create conversation stream with the given audio source and sink.
    conversation_stream = audio_helpers.ConversationStream(
        source=audio_device,
        sink=audio_device,
        iter_size=3200,
        sample_width=2)

    device_handler = device_helpers.DeviceRequestHandler(device_id)

    @device_handler.command('action.devices.commands.OnOff')
    def onoff(on):
        if on:
            logging.info('Turning device on')
        else:
            logging.info('Turning device off')

    @device_handler.command('action.devices.commands.BrightnessAbsolute')
    def start_stop(value):
        logging.info(f'Setting brightness to {value}')

    with Assistant('en-US', model_id, device_id, conversation_stream, False, grpc_channel, 60 * 3 + 5, device_handler) as assistant:
        while True:
            logging.info('Waiting for activation request')
            req = queue.get()
            if req is False:
                queue.task_done()
                break

            logging.info('Activating assistant')
            api.active = True
            try:
                while assistant.assist():
                    pass
            finally:
                api.active = False
                logging.info('Assistant has finished')

                queue.task_done()
                with queue.mutex:
                    queue.queue.clear()


def register_device(credentials):
    model_id = device_model_id
    dev_id = device_id
    try:
        with open('/srv/assistant/device.json') as f:
            device = json.load(f)
            dev_id = device['id']
            model_id = device['model_id']
            logging.info(f"Using device model {model_id} and device id {dev_id}")
    except Exception as e:
        logging.warning('Device config not found: %s' % e)
        logging.info('Registering device')
        if not model_id:
            raise Exception('Missing device model id')

        if not project_id:
            raise Exception('Missing project id')

        device_base_url = (f'https://{assistant_api_endpoint}/v1alpha2/projects/{project_id}/devices')
        dev_id = str(uuid.uuid1())
        payload = {
            'id': dev_id,
            'model_id': model_id,
            'client_type': 'SDK_SERVICE'
        }
        session = google.auth.transport.requests.AuthorizedSession(credentials)
        r = session.post(device_base_url, data=json.dumps(payload))
        if r.status_code != 200:
            raise Exception(f'Failed to register device: {r.text}')

        logging.info(f'Device registered: {dev_id}')
        with open('/srv/assistant/device.json', 'w') as f:
            json.dump(payload, f)

    return (model_id, dev_id)


def main():
    global api

    credentials, http_request = load_credentials()

    model_id = device_model_id
    dev_id = device_id
    if not dev_id or not model_id:
        model_id, dev_id = register_device(credentials)

    api = DBusAPI()
    try:
        api.start()
        try:
            run_assistant(api, credentials, http_request, model_id, dev_id)
        except KeyboardInterrupt:
            pass
    finally:
        api.quit()
        api.join()


logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)
if __name__ == '__main__':
    main()
