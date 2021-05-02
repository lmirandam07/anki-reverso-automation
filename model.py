from typing import ClassVar
import genanki

STYLE_TEMPLATE = """
.card {
    font-family: arial;
    font-size: 20px;
    text-align: center;
    color: black;
    background-color: white;
}
"""

VOCAB_REVERSE_TEMPLATE = genanki.Model(
    1613951331974,
    "Goethe Vocab List (ESP)",
    fields=[
        {"name": "de_word"},
        {"name": "de_sentence"},
        {"name": "de_audio"},
        {"name": "es_word"},
        {"name": "es_sentence"},
        {"name": "es_note"},
    ],

    templates= [
        {
            "name": "Front",
            "qfmt": "{{de_word}}"
                    "{{#de_sentence}}"
                    "<br><br>"
                    "<i>{{de_sentence}}</i>"
                    "{{/de_sentence}}"
                    "{{de_audio}}",
            "afmt": "{{FrontSide}}"
                    "<hr id=answer>"
                    "{{es_word}}"
                    "{{#es_sentence}}"
                    "<br><br>"
                    "<i>{{es_sentence}}</i>"
                    "{{/es_sentence}}"
                    "{{#es_note}}"
                    "<br><br>"
                    "<small>{{es_note}}</small>"
                    "{{/es_note}}"
        }
    ],
    css=STYLE_TEMPLATE
)