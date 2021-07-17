import csv
import genanki
from pathlib import Path
from random import shuffle
from model import VOCAB_REVERSE_TEMPLATE
from reverso_scraper import csv_words_creator

class DeutschNote(genanki.Note):
    @property
    def guid(self):
        return genanki.guid_for(self.fields[0])

def main():
    '''
    Create Anki Deck
    '''
    num_new_words = csv_words_creator()

    if num_new_words:
        csv_file = Path("./words_list.csv")
        package_file = "Deutsch.apkg"
        deck = genanki.Deck(1613951331974, "Deutsch")
        deutsch_deck = genanki.Package(deck)

        with open(csv_file, 'r', encoding='utf-8') as file:
            words = list(csv.reader(file))
            # Discard header of csv from the search
            words.pop(0)
            start_from = len(words) - num_new_words
            words = words[start_from:]
            shuffle(words)
            for word in words:
                # The 4th is the position of audio on the row
                word_audio = word[4]
                if word_audio:
                    audio_path = Path(f"./audios/{word_audio}")
                    deutsch_deck.media_files.append(audio_path)
                    word[4] = f"[sound:{word_audio}]"

                note = DeutschNote(
                    model = VOCAB_REVERSE_TEMPLATE,
                    fields= [*word[:-1]], # The last field is the tag
                    tags=[word[-1]]
                )

                deck.add_note(note)

        deutsch_deck.write_to_file(package_file)
        print(f"Total de notas añadidas: {len(deck.notes)}")



if __name__ == '__main__':
    main()