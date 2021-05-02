import csv
import logging
import requests
from uuid import uuid4
from pathlib import Path
from random import choice
from decouple import config
from bs4 import BeautifulSoup
from xml.etree import ElementTree


headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:87.0) Gecko/20100101 Firefox/87.0'
}
azure_access_token = ''


def reverso_request(start, length):
    base_url = f"https://context.reverso.net/bst-web-user/user/favourites/shared"

    params = {
        'userName': 'lmirandam07',
        'start': start,
        'length': length,
        'order': 10
    }

    try:
        request = requests.get(base_url, params=params, headers=headers)
        request.raise_for_status()

        return request.json()
    except requests.exceptions.HTTPError as e:
        print(e)


# Function to drop the duplicated words from the JSON
def words_filter(words, csv_headers):
    csv_file = Path("./words_list.csv")
    csv_file.touch(exist_ok=True)
    empty_file = False

    with open(csv_file, 'r') as file:
        reader = list(csv.reader(file))

        # If the file only has headers
        if len(reader) == 1 or reader[2] != "\n":
            return words

        # If the file is empty
        if len(reader) < 1:
            empty_file = True
        elif len(reader) >= 2:
            # Get the last german word, but only the word, without its article or plural
            last_word_de = reader[-1][0].split(" ")[1]

    if empty_file:
        with open(csv_file, 'w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)

            writer.writerow(csv_headers.keys() + "\n")
            return words

    last_updated_idx = words.index(list(filter(
        lambda w: w['srcText'] == last_word_de if w['srcLang'] == 'de' else w['trgText'] == last_word_de, words))[0])

    return words[:last_updated_idx]


def get_word_tag(de_word):
    tags = ('adjetivo', 'sustantivo', 'adverbio', 'verbo')
    reverso_url = f"https://context.reverso.net/traduccion/aleman-espanol/{de_word}"

    try:
        req = requests.get(reverso_url, headers=headers)
        soup = BeautifulSoup(req.text, "html.parser")
        word_tag = soup.select(
            "#pos-filters button")[0].text.strip().lower() or ""

        if word_tag not in tags:
            print(de_word, word_tag)
            return ""

        return word_tag
    except requests.exceptions.HTTPError as e:
        print(e)


def get_noun_article(de_word):
    leo_url = f"https://dict.leo.org/alem%C3%A1n-espa%C3%B1ol/{de_word}"

    try:
        req = requests.get(leo_url, headers=headers)
        soup = BeautifulSoup(req.text, "html.parser")
        de_noun = soup.select("#section-subst td[lang='de'] samp")

        de_article = de_noun[0].text.split(' ')[0] or ''
        de_plural = de_noun[0].find('small').text or ''
        de_word = f"{de_article} {de_word} - {de_plural}"
        return de_word

    except requests.exceptions.HTTPError as e:
        print(e)


def get_access_token(sub_key, region):
    fetch_token_url = f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    headers = {
        'Ocp-Apim-Subscription-Key': sub_key
    }

    try:
        response = requests.post(fetch_token_url, headers=headers)
        return str(response.text)
    except requests.exceptions.HTTPError as e:
        print(e)


def get_sentence_audio(de_sentence):
    AZURE_API_KEY = config('AZURE_API_KEY')
    AZURE_REGION = config('AZURE_REGION')
    global azure_access_token

    if not azure_access_token:
        azure_access_token = get_access_token(AZURE_API_KEY, AZURE_REGION)

    try:
        langs_and_voices = {
            'de-DE': ('de-DE-ConradNeural', 'de-DE-KatjaNeural'),
            'de-AT': ('de-AT-JonasNeural', 'de-AT-IngridNeural'),
            'de-CH': ('de-CH-LeniNeural', 'de-CH-JanNeural')
        }
        # From the list of voices in german in the API, randomly select one
        lang_choice = choice(list(langs_and_voices.keys()))
        voice_choice = choice(langs_and_voices[lang_choice])

        rate = 0
        pitch = 0

        azure_api_url = f'https://{AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1'
        headers = {
            'Authorization': f'Bearer {azure_access_token}',
            'Content-Type': 'application/ssml+xml',
            'X-Microsoft-OutputFormat': 'audio-24khz-96kbitrate-mono-mp3',
            'User-Agent': 'reverso-anki-automation'
        }
        # Create XML format that uses the API to make the translation
        xml_body = ElementTree.Element('speak', version='1.0')
        xml_body.set('{http://www.w3.org/XML/1998/namespace}lang', lang_choice)

        voice = ElementTree.SubElement(xml_body, 'voice')
        voice.set('{http://www.w3.org/XML/1998/namespace}lang', lang_choice)
        voice.set(
            'name', voice_choice)

        prosody = ElementTree.SubElement(voice, 'prosody')
        prosody.set('rate', f'{rate}%')
        prosody.set('pitch', f'{pitch}%')
        prosody.text = de_sentence

        body = ElementTree.tostring(xml_body)

        response = requests.post(azure_api_url, headers=headers, data=body)

        if response.status_code in range(200, 300):
            audio_folder = Path("./audios")
            audio_folder.mkdir(exist_ok=True)
            audio_file_name = Path(f"azure-{str(uuid4())}.mp3")
            audio_file_path = Path.joinpath(audio_folder, audio_file_name)

            if not audio_file_path.exists():
                with open(audio_file_path, 'wb') as audio:
                    audio.write(response.content)

                return audio_file_name.name

        return ''

    except requests.exceptions.HTTPError as e:
        print(e)


def get_words_list(word, words_dict):
    words_dict_c = words_dict.copy()
    # If src lang is german, then return the first order otherwise change the order
    def language_order(lang): return (
        'src', 'trg') if lang == 'de' else ('trg', 'src')

    de_order, es_order = language_order(word['srcLang'])
    words_dict_c['de_word'] = word[f'{de_order}Text']
    words_dict_c['es_word'] = word[f'{es_order}Text']
    # To remove <em> tags
    words_dict_c['de_sentence'] = BeautifulSoup(
        word[f'{de_order}Context'], features="html.parser").get_text()
    words_dict_c['es_sentence'] = BeautifulSoup(
        word[f'{es_order}Context'], features="html.parser").get_text()

    words_dict_c['tags'] = get_word_tag(words_dict_c['de_word'])

    if words_dict_c['tags'] == 'sustantivo':
        words_dict_c['de_word'] = get_noun_article(words_dict_c['de_word'])

    words_dict_c['de_audio'] = get_sentence_audio(words_dict_c['de_sentence'])
    return words_dict_c


def save_words_csv(words_list):
    csv_file = Path("./words_list.csv")
    with open(csv_file, 'a', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=words_list[0].keys())
        for w in words_list:
            writer.writerow(w)
    # TODO: Loggear la cantidad de palabras que se han añadido nuevas
    print(
        f'Se ha completado el proceso correctamente, se han añadido {len(words_list)} palabras')


def csv_words_creator():
    # logging.basicConfig(filename='scraper.log', level=logging.INFO)
    words_dict = {
        'de_word': '',
        'de_sentence': '',
        'es_word': '',
        'es_sentence': '',
        'de_audio': '',
        'tags': ''
    }
    start = 0
    length = 10
    data = reverso_request(start, length)
    words_results = data['results']
    num_total_results = data['numTotalResults']
    if num_total_results > length:
        # Starts the requests in the end of the previus and make another with all the remaining words
        start = length
        length = num_total_results - length
        data = reverso_request(start, length)
        words_results.extend(data['results'])

    filtered_words = words_filter(words_results, words_dict)

    words_dict_list = [get_words_list(f_w, words_dict)
                       for f_w in filtered_words]

    save_words_csv(words_dict_list)
    return True


if __name__ == '__main__':
    csv_words_creator()
