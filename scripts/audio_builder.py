import time
from typing import cast
import requests
from uuid import uuid4
from random import choice
from pathlib import Path
from decouple import AutoConfig
from xml.etree import ElementTree

config = AutoConfig(search_path='../files/.env')


class AzureAudio:
    def __init__(self):
        self._api_key = config('AZURE_API_KEY', cast=str)
        self._region = config('AZURE_REGION', cast=str)
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
            return response.content.decode('utf-8')
        except requests.exceptions.HTTPError as e:
            print(e)

    def get_audio(self, text, lang):
        azure_api_key = self._api_key
        azure_region = self._region
        azure_access_token = self.get_access_token(azure_api_key, azure_region)

        if not azure_access_token:
            return ''

        try:
            langs_and_voices = self.get_voices(lang)
            # From the list of voices in german in the API, randomly select one
            lang_choice = choice(list(langs_and_voices.keys()))
            voice_choice = choice(langs_and_voices[lang_choice])

            rate = 0
            pitch = 0

            azure_api_url = f'https://{azure_region}.tts.speech.microsoft.com/cognitiveservices/v1'
            headers = {
                'Authorization': f'Bearer {azure_access_token}',
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
            if response.status_code == 429:
                retry_after = response.headers.get('Retry_After')
                time.sleep(int(retry_after) if retry_after else 60)
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

            return ''

        except requests.exceptions.HTTPError as e:
            print(e)
