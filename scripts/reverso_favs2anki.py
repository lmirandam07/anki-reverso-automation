import csv
import logging
import requests
from pathlib import Path
from random import shuffle
from bs4 import BeautifulSoup
from datetime import datetime
from audio_builder import AzureAudio

logging.basicConfig(filename='../files/main.log', level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')

BASE_URL = "https://context.reverso.net/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:87.0) Gecko/20100101 Firefox/87.0'
}


class ReversoFavs2Anki(object):
    def __init__(self, username: str,
                 audio: bool = False,
                 src_lang: str = 'de',
                 trg_lang: str = 'es',
                 headers=None) -> None:
        self._audio_builder = None
        self.username = username
        self.start = 0
        self.length = 50
        self.src_lang = src_lang
        self.trg_lang = trg_lang
        self.audio = audio
        self.headers = headers if headers != None else HEADERS

    @property
    def _get_audio_builder(self):
        if self._audio_builder is None:
            self._audio_builder = AzureAudio()

        return self._audio_builder

    def proccess_favs(self):
        logging.info('Proccess Started')
        data = self.get_favs(self.username, self.start, self.length)
        content = data['results']
        total_results = data['numTotalResults']

        if total_results > self.length:
            new_start = self.length
            new_length = total_results - self.length
            data = self.get_favs(self.username, new_start, new_length)
            content.extend(data['results'])

        logging.info('Favs scraped successfully')
        words_list, last_date = self.create_word_list(content)

        if len(words_list) < 1:
            logging.info('No new words were added to Reverso')
            return False

        self.create_csv(words_list)
        self.update_last_exec_date(last_date)

        return True

    def create_csv(self, words_list):
        csv_file = Path("../files/words_list.csv")
        if csv_file.exists():
            csv_file.unlink()

        csv_file.touch()
        fieldnames = list(words_list[0].keys())

        with open(csv_file, 'w', encoding='utf-8', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for w in words_list:
                writer.writerow(w)

        logging.info(
            f'{len(words_list)} words were added to csv file')

    def create_word_list(self, data):
        src_l = self.src_lang
        trg_l = self.trg_lang
        words_dict = {}
        words_list = []

        # Remove html tags in the sentences of the API
        def clean_sentence(w): return BeautifulSoup(
            w, features="html.parser").get_text()
        # If src lang is the same as the class attr, then return the first order otherwise change the order
        def lang_order(lang, src_lang): return (
            'src', 'trg') if lang == src_lang else ('trg', 'src')

        last_date_exec = self.get_last_exec_date()
        if last_date_exec:
            last_date_exec = datetime.strptime(
                last_date_exec, "%Y-%m-%dT%H:%M:%SZ")

        for word in data:
            word_date = datetime.strptime(
                word['creationDate'], "%Y-%m-%dT%H:%M:%SZ")

            if word_date <= last_date_exec:
                break

            src_order, trg_order = lang_order(word['srcLang'], src_l)
            words_dict = {
                f'{src_l}_word': word[f'{src_order}Text'],
                f'{trg_l}_word': word[f'{trg_order}Text'],
                f'{src_l}_sentence': clean_sentence(word[f'{src_order}Context']),
                f'{trg_l}_sentence': clean_sentence(word[f'{trg_order}Context']),
                f'{src_l}_audio': '',
                'tag': '',
            }

            tag = self.get_word_tag(
                words_dict[f'{src_l}_word'], words_dict[f'{trg_l}_word'])
            words_dict['tag'] = tag

            if tag == 'sustantivo' and src_l == 'de':
                words_dict[f'{src_l}_word'] = self.get_noun_article(
                    words_dict[f'{src_l}_word'])

            if self.audio:
                words_dict[f'{src_l}_audio'] = self.get_sentence_audio(
                    words_dict[f'{src_l}_sentence'])

            words_list.append(words_dict)

        # Get the date of the last word added to reverso
        last_date = data[0]['creationDate']

        return words_list, last_date

    def get_favs(self, username: str, start: int, length: int):
        favs_url = "bst-web-user/user/favourites/shared"
        params = {
            'userName': username,
            'start': start,
            'length': length,
            'order': 10
        }

        try:
            req = requests.get(BASE_URL + favs_url,
                               params=params, headers=self.headers)
            req.raise_for_status()

            return req.json()
        except requests.exceptions.HTTPError as e:
            logging.error("Exception ocurred when trying to get favs")

    def get_word_tag(self, src_word, trg_word):
        tags = {'adj.': 'adjetivo',
                'nn.': 'sustantivo',
                'nm.': 'sustantivo',
                'nf.': 'sustantivo',
                'adv.': 'adverbio',
                'v.': 'verbo',
                'conj./prep.': 'conjuncion/preposicion'}

        query_url = "bst-query-service"
        data = {
            'source_lang': self.src_lang,
            'source_text': src_word,
            'target_lang': self.trg_lang,
            'target_text': trg_word,
            'mode': 0,
            'npage': 1,
        }

        try:
            req = requests.post(BASE_URL + query_url,
                                json=data, headers=self.headers)
            req.raise_for_status()
            json = req.json()

            if len(json['dictionary_entry_list']):
                tag = json['dictionary_entry_list'][0]['pos']

                if tag in tags.keys():
                    tag = tags[tag] or ''
                    return tag

            return ''
        except requests.exceptions.HTTPError as e:
            logging.error("Exception ocurred when trying to get word tag")

    def get_noun_article(self, de_noun):
        leo_url = f"https://dict.leo.org/alemán-español/{de_noun}"

        try:
            req = requests.get(leo_url, headers=self.headers)
            soup = BeautifulSoup(req.text, "html.parser")
            de_noun_selector = soup.select("#section-subst td[lang='de'] samp")

            # Lambda to return empty string if article or plural form is not found
            xstr = lambda s: '' if s is None else str(s.text)

            de_article = xstr(de_noun_selector[0]).split(' ')[0]
            de_plural = xstr(de_noun_selector[0].find('small'))
            de_noun_complete = f"{de_article} {de_noun} - {de_plural}"

            return de_noun_complete

        except requests.exceptions.HTTPError as e:
            logging.error("Exception ocurred when trying to get noun article")

    def get_sentence_audio(self, sentence):
        audio_builder = self._get_audio_builder
        audio_name = audio_builder.get_audio(sentence, self.src_lang)

        return audio_name

    def get_last_exec_date(self):
        file_path = Path("../files/exec_date.txt")

        if not file_path.exists():
            file_path.touch()
            logging.info("There is not previous execution date")
            return

        with open(file_path, 'r') as file:
            date = file.readline()

        logging.info(f"The previous execution date is: {date}")
        return date

    def update_last_exec_date(self, last_date):
        file_path = Path("../files/exec_date.txt")

        if file_path.exists():
            file_path.unlink()
        file_path.touch()

        with open(file_path, 'w') as file:
            file.write(str(last_date))

        logging.info(f"The new last execution date is: {str(last_date)}")
        return


if __name__ == '__main__':
    rev = ReversoFavs2Anki('lmirandam07', audio=True, headers=HEADERS)
    rev.proccess_favs()
