import csv
import model
import time
import logging
import genanki
from pathlib import Path
from random import shuffle
from win10toast import ToastNotifier
from reverso_favs2anki import ReversoFavs2Anki

logging.basicConfig(filename='main.log', level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')


class Note(genanki.Note):
    @property
    def guid(self):
        return genanki.guid_for(self.fields[0])


def main():
    '''
    Create Anki Deck
    '''
    csv_file = Path("../files/words_list.csv")
    deck = genanki.Deck(model.DECK_ID, model.DECK_NAME)
    deutsch_deck = genanki.Package(deck)

    with open(csv_file, 'r', encoding='utf-8') as file:
        words = list(csv.reader(file))
        # Discard header of csv from the search
        words.pop(0)
        shuffle(words)
        for word in words:
            # The 4th is the position of audio on the row
            word_audio = word[4]
            if word_audio:
                audio_path = Path(f"../files/audios/{word_audio}")
                deutsch_deck.media_files.append(audio_path)
                word[4] = f"[sound:{word_audio}]"

            note = Note(
                model=model.VOCAB_REVERSE_TEMPLATE,
                fields=[*word[:-1]],  # The last field is the tag
                tags=[word[-1]]
            )

            deck.add_note(note)

    deutsch_deck.write_to_file(f"../files/{model.PACKAGE_NAME}")
    logging.info(
        f"Total number of notes appended to anki deck: {len(deck.notes)}")
    toaster = ToastNotifier()
    toaster.show_toast("ReversoFavs2Anki",
                       f"Script executed correctly, {len(deck.notes)} notes were added",
                       duration=30)

    while toaster.notification_active():
        time.sleep(0.1)


if __name__ == '__main__':
    rev = ReversoFavs2Anki('lmirandam07', audio=True)
    if rev.proccess_favs():
        main()
