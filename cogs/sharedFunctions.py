import json
import re

"""funzioni condivise tra varie cogs"""

weekdays = {
    0: "mon",
    1: "tue",
    2: "wed",
    3: "thu",
    4: "fri",
    5: "sat",
    6: "sun"
}

class BannedWords():

    banned_words = []

    def __init__(self):
        try:
            with open('banned_words.json','r') as file:
                BannedWords.banned_words = json.load(file)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            with open('banned_words.json','w+') as file:
                BannedWords.banned_words = []

    def add(word):
        BannedWords.banned_words.append(word)

    def remove(word):
        BannedWords.banned_words.remove(word)

    def contains_banned_words(text):
        """Implementa il controllo sulle parole bannate tramite regex"""
        text_to_check = text.lower()
        text_to_check = re.sub("0", "o", text_to_check)
        text_to_check = re.sub("1", "i", text_to_check)
        text_to_check = re.sub("5", "s", text_to_check)
        text_to_check = re.sub("2", "z", text_to_check)
        text_to_check = re.sub("8", "b", text_to_check)
        text_to_check = re.sub("4", "a", text_to_check)
        text_to_check = re.sub("3", "e", text_to_check)
        text_to_check = re.sub("7", "t", text_to_check)
        text_to_check = re.sub("9", "g", text_to_check)
        for word in BannedWords.banned_words:
            regex_word = '+ *\W*'.join(word)
            x = re.search(regex_word, text_to_check)
            if x is not None:
                return True
        return False

def update_json_file(data, json_file):
    """Scrive su file le modifiche apportate all' archivio json con il conteggio dei messaggi"""
    with open(json_file, 'w') as file:
        json.dump(data, file, indent=4)
        
def count_messages(item):
    """Ritorna il conteggio totale dei messaggi dei 7 giorni precedenti"""
    count = 0
    for i in weekdays:
        count += item[weekdays.get(i)]
    return count
