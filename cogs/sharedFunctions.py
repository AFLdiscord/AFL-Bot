import json
import re
from datetime import datetime, timedelta

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
    """Ritorna il conteggio totale dei messaggi dei 7 giorni precedenti. Il parametro item è un dizionario."""
    count = 0
    for i in weekdays:
        if i != datetime.today().weekday():
            count += item[weekdays.get(i)]
    count += item["counter"]
    return count

def clean(item):
    """Si occupa di controllare il campo last_message_date e sistemare di conseguenza il conteggio dei singoli giorni"""
    if (item["last_message_date"] is None) or (item["last_message_date"] == datetime.date(datetime.now()).__str__()):      
        #(None) tecnicamente previsto da add_warn se uno viene warnato senza aver mai scritto
        #(Oggi) vuol dire che il bot è stato riavviato a metà giornata non devo toccare i contatori
        return
    elif item["last_message_date"] == datetime.date(datetime.today() - timedelta(days=1)).__str__:
        #messaggio di ieri, devo salvare il counter nel giorno corrispondente
        day = weekdays[datetime.date(datetime.today() - timedelta(days=1)).weekday()]
        d[day] = counter
        d["counter"] = 0
    else:
        #devo azzerare tutti i giorni della settimana tra la data segnata (esclusa) e oggi (incluso)
        #in teoria potrei anche eliminare solo il giorno precedente contando sul fatto che venga eseguito tutti i giorni
        #ma preferisco azzerare tutti in caso di downtime di qualche giorno
        last_day = datetime.date(datetime.strptime(item["last_message_date"], '%Y-%m-%d')).weekday()
        today = datetime.today().weekday()
        while(last_day != today):
            last_day += 1
            if last_day > 6:
                last_day = 0
            item[weekdays[last_day]] = 0
