import time
import logging
import requests
from uuid import uuid4
from random import choice
from pathlib import Path
from decouple import AutoConfig
from xml.etree import ElementTree


logging.basicConfig(filename='../files/main.log', level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
try:
    config = AutoConfig(search_path='../files/.env')
    AZURE_API_KEY = config('AZURE_API_KEY', cast=str)
    AZURE_REGION = config('AZURE_REGION', cast=str)

except Exception as e:
    logging.error("Exception occurred when trying to load .env vars")

class AzureAudio:
    def __init__(self):
        self._api_key = AZURE_API_KEY
        self._region = AZURE_REGION
        self.access_token = ''
        self._voices = {
            'de': {
                'de-DE': ('de-DE-ConradNeural', 'de-DE-KatjaNeural'),
                'de-AT': ('de-AT-JonasNeural', 'de-AT-IngridNeural'),
            }
        }

    def get_voices(self, lang=None):
        if lang != None:
            return self._voices[lang]

        return self._voices

    def get_access_token(self, sub_key, region):
        fetch_token_url = f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
        headers = {
            'Ocp-Apim-Subscription-Key': sub_key,
            'User-Agent': 'reverso_favs2anki'
        }

        try:
            response = requests.post(fetch_token_url, headers=headers)
            self.access_token = response.content.decode('utf-8')
            return self.access_token

        except requests.exceptions.HTTPError as e:
            logging.error("Exception occurred when trying to get access token")

    def get_audio(self, text, lang):
        azure_api_key = self._api_key
        azure_region = self._region

        if not self.access_token:
            access_token = self.get_access_token(azure_api_key, azure_region)

            if not access_token:
                logging.error("Could not get azure access token")
                return ''
        else:
            access_token = self.access_token

        try:
            langs_and_voices = self.get_voices(lang)
            # From the list of voices in the API, randomly select one
            lang_choice = choice(list(langs_and_voices.keys()))
            voice_choice = choice(langs_and_voices[lang_choice])

            rate = 0
            pitch = 0

            azure_api_url = f'https://{azure_region}.tts.speech.microsoft.com/cognitiveservices/v1'
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/ssml+xml',
                'X-Microsoft-OutputFormat': 'audio-24khz-96kbitrate-mono-mp3',
                'User-Agent': 'reverso_favs2anki'
            }
            # Create XML format that uses the API to make the translation
            xml_body = ElementTree.Element('speak', version='1.0')
            xml_body.set(
                '{http://www.w3.org/XML/1998/namespace}lang', lang_choice)

            voice = ElementTree.SubElement(xml_body, 'voice')
            voice.set('{http://www.w3.org/XML/1998/namespace}lang', lang_choice)
            voice.set(
                'name', voice_choice)

            prosody = ElementTree.SubElement(voice, 'prosody')
            prosody.set('rate', f'{rate}%')
            prosody.set('pitch', f'{pitch}%')
            prosody.text = text

            body = ElementTree.tostring(xml_body)

            response = requests.post(
                azure_api_url, headers=headers, data=body)

            # If there are too manny requests try again after some time
            if response.status_code not in range(200, 300):
                retry_after = response.headers.get('Retry_After')
                time.sleep(int(retry_after) if retry_after else 10)
                response = requests.post(
                    azure_api_url, headers=headers, data=body)


            if response.status_code in range(200, 300):
                audio_folder = Path("../files/audios")
                audio_folder.mkdir(exist_ok=True)
                audio_file_name = Path(f"azure-{str(uuid4())}.mp3")
                audio_file_path = Path.joinpath(audio_folder, audio_file_name)

                if not audio_file_path.exists():
                    with open(audio_file_path, 'wb') as audio:
                        audio.write(response.content)
                        audio.close()

                    return audio_file_name.name

            logging.error(f'Could not create the audio for the text "{text}"')
            return ''

        except requests.exceptions.HTTPError as e:
            logging.error("Exception occurred when trying to get access token")
