from google.cloud import texttospeech
import wave
from dotenv import load_dotenv


def text_to_speech_to_wav():
    # Set up Google Cloud TTS client
    client = texttospeech.TextToSpeechClient()

    # Input text from user
    text = input("Enter the text you want to convert to speech: ")

    # Set up the synthesis input
    synthesis_input = texttospeech.SynthesisInput(text=text)

    # Configure the voice settings
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",  # Change this to the desired language code
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    )

    # Configure the audio settings
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16  # WAV format
    )

    # Perform the text-to-speech request
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    # Save the audio to a WAV file
    output_file = "output.wav"
    with wave.open(output_file, "wb") as wav_file:
        # Set the WAV file parameters
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit samples
        wav_file.setframerate(24000)  # 24kHz sample rate

        # Write the audio data
        wav_file.writeframes(response.audio_content)

    print(f"The text has been converted to speech and saved as '{output_file}'.")

# Run the program
if __name__ == "__main__":
    load_dotenv()
    text_to_speech_to_wav()
