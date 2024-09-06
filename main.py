import speech_recognition as sr
import time
import requests
from openai import OpenAI
from pydub import AudioSegment
from playsound import playsound
import io
import json  # Import the JSON module to handle JSON responses

client = OpenAI()

def recognize_speech_with_openai():
    try:
        audio_file = open("audio.mp3", "rb")
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        return transcription.text
    except Exception as e:
        return f"Error: {e}"

def send_to_server(transcription):
    try:
        # URL of the server endpoint
        url = "http://127.0.0.1:5000/chat"
        # Data to be sent in the POST request
        data = {'query': transcription}
        # Make a POST request
        response = requests.post(url, data=data)
        # Check the response
        if response.status_code == 200:
            # Parse the JSON response and extract the 'result' field
            response_json = response.json()
            return response_json.get("result", "Error: 'result' field not found in the response.")
        else:
            return f"Error: Server responded with status code {response.status_code}"
    except Exception as e:
        return f"Error: Could not send data to server; {e}"

def read(text):
    """Uses OpenAI's TTS to convert text to speech and plays it."""
    try:
        with client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice="onyx",
            input=text,
        ) as response:
            response.stream_to_file("speech.mp3")

        playsound('speech.mp3')
    except Exception as e:
        print(f"Error in text-to-speech: {e}")

def listen():
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()

    with microphone as source:
        recognizer.adjust_for_ambient_noise(source)
        print("Adjusted for ambient noise. Start speaking.")

        try:
            print("Listening...")
            audio = recognizer.listen(source, timeout=5)
            print("Processing...")

            wav_data = io.BytesIO(audio.get_wav_data())
            audio_segment = AudioSegment.from_wav(wav_data)
            audio_segment.export("audio.mp3", format="mp3")

            transcription = recognize_speech_with_openai()
            print("You said: " + transcription)

            if transcription:
                # Send the transcription to the server
                server_response = send_to_server(transcription)
                print("Server response: {}".format(server_response))

                # Read the server's response aloud
                read(server_response)
            else:
                print("No transcription returned.")

        except sr.WaitTimeoutError:
            print("Timeout, no speech detected.")
        except sr.UnknownValueError:
            print("Could not understand the audio.")
        except sr.RequestError as e:
            print(f"Could not request results; {e}")

def continuous_listen():
    """Continuously listens and processes speech every 10 seconds."""
    while True:
        listen()  # Call the listen function to capture and process speech
        print("Pausing for 10 seconds...")
        time.sleep(10)  # Wait for 10 seconds before the next iteration

if __name__ == '__main__':
    continuous_listen()  # Start the continuous listening process
