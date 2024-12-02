from steve import *

chirp = AudioClip('sounds/chirp.wav')
wake = WakeWord()
stt = SpeechToText()
tts = TextToSpeech()
gpt = ChatGPT()


while True:
    print('Waiting for "Hey Steve"...', end='', flush=True)
    wake.detect()
    print('done.')
    chirp.play()

    for text in stt.recognize():
        print(f'##{text}##')
        if isinstance(text, str):
            if text.startswith('wake up'):
                stt.stop()
                for word in gpt.respond('Good morning!'):
                    tts.say(word)
            elif text.startswith('sleep'):
                stt.stop()
                for word in gpt.respond('Good night!'):
                    tts.say(word)
            elif text.startswith('high five'):
                stt.stop()
                for word in gpt.respond('High five!'):
                    tts.say(word)
            elif text.startswith('reset'):
                stt.stop()
                for word in gpt.respond('Resetting!'):
                    tts.say(word)
            elif text.startswith('move'):
                print(gpt.program(text))

