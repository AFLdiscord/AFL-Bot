"""Funzionalità condivise tra le diverse cog per facilitare la manutenzione. In particolare:
Classi:
- BannedWords per gestione delle parole bannate
- Config per la gestione dei parametri di configuarazione del bot

Funzioni:
- update_json_file per salvare in json le modifiche
- count_messages conta i messaggi presenti nei giorni della settimana e counter
- count_consolidated_messages conta solo i messaggi già salvati nel giorno
- clean aggiorna i contatori dei vari giorni controllando la data
"""

import json
import re
from datetime import datetime, timedelta
from typing import List

#utile per passare dal giorno della settimana restituito da weekday() direttamente
#al campo corrispondente nel dizionario del json
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
    """Gestione delle parole bannate. In particolare si occupa di caricare la lista dal rispettivo
    file banned_words.json che si aspetta di trovare nella stessa cartella del bot. L'elenco è
    salvato in un attributo di classe e tutti i metodi sono statici. Non è fornito un metodo
    __init__ poichè non ci si aspetta che questa classe debba essere istanziata, occorre
    sfruttare metodi e attributi di classe.

    Attributes
    -------------
    banned_words: List[str] attributo di classe contenente l'elenco delle parole bannate

    Methods
    -------------
    load()  carica dal file banned_words.json l'elenco della parole bannate
    add(word) aggiunge la parola all'elenco
    remove(word) rimuove la parola dall'elenco
    contains_banned_words(text) controlla se sono presenti parole bannate nel testo fornito
    """

    banned_words = []

    @staticmethod
    def to_string() -> str:
        """Rappresentazione dell'attributo banned_words come stringa. Fatto così invece
        che con __repr__ o __str__ perchè la classe non viene istanziata.

        :returns: la stringa con tutte le parole bannate
        :rtype: str
        """
        string = ''
        for word in BannedWords.banned_words:
            string += word + '\n'
        if string == '':
            string = 'Nessuna parola attualmente in elenco.'
        return string

    @staticmethod
    def load() -> None:
        """Carica l'elenco delle parole bannate dal file banned_words.json
        Se il file non è presente o incorre in un errore nella procedura l'elenco rimane vuoto.
        """
        try:
            with open('banned_words.json','r') as file:
                BannedWords.banned_words = json.load(file)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            with open('banned_words.json','w+') as file:
                BannedWords.banned_words = []

    @staticmethod
    def add(word: str) -> None:
        """Aggiunge una stringa all'elenco banned_words

        :param word: la parola da aggiungere
        """
        BannedWords.banned_words.append(word)

    @staticmethod
    def remove(word: str) -> None:
        """Rimuove una stringa all'elenco banned_words

        :param word: la parola da rimuovere
        """
        BannedWords.banned_words.remove(word)

    @staticmethod
    def contains_banned_words(text: str) -> bool:
        """Controlla se sono presenti parole bannate tramite regex.

        :param text: il testo da controllare

        :returns: se il testo contiene o meno una parola bannata
        :rtype: bool
        """
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
            match = re.search(regex_word, text_to_check)
            if match is not None:
                return True
        return False

class Config():
    """Gestione dei parametri di configurazione del bot. Salva tutti i parametri in un dizionario
    che può essere usato dal resto del bot per svolgere la sua funzione. I parametri possono essere
    aggiornati in ogni momento ricaricando i valori dal file config.json che si aspetta di trovare
    nella cartella del bot. Non è fornito un metodo __init__ poichè questa classe è pensata solo per
    utilizzare metodi e attributi statici.

    Attributes
    -------------
    config: dict attributo di classe che conserva i parametri di configurazione in un dizionario

    Methods
    -------------
    load()  carica i valori dal file config.json
    """

    config = {}

    @staticmethod
    def to_string() -> str:
        """Rappresentazione della configurazione del bot come stringa. Fatto così invece
        che con __repr__ o __str__ perchè la classe non viene istanziata.

        :returns: la configurazione corrente del bot
        :rtype: str
        """
        string = ''
        for key in Config.config:
            string += key + ' : ' + str(Config.config[key]) + '\n'
        return string

    @staticmethod
    def load() -> bool:
        """Carica i parametri dal file config.json nell'attributo di classe config. Il formato del
        file deve essere quello specificato nel template (vedi config.template). Deve essere
        chiamato all'avvio del bot. Ritorna un booleano con l'esito.
        In caso di fallimento mantiene inalterato il config attuale.

        :returns: vero o falso a seconda dell'esito
        :rtype: bool
        """
        try:
            with open('config.json', 'r') as file:
                data = json.load(file)
                Config._load_config(data)
                print('configurazione ricaricata correttamente')
                return True
        except (FileNotFoundError, json.decoder.JSONDecodeError) as e:
            print(e)
            print('errore nella ricarica della configurazione, mantengo configurazione precedente')
            return False

    @staticmethod
    def _load_config(data) -> None:
        """Converte i valori letti dal dizionario nei tipi corretti. Chiamato dalla load, non
        utilizzare direttamente questo metodo.
        """
        Config.config['guild_id'] = int(data['guild_id'])
        Config.config['main_channel_id'] = int(data['main_channel_id'])
        Config.config['presentation_channel_id'] = int(data['presentation_channel_id'])
        Config.config['welcome_channel_id'] = int(data['welcome_channel_id'])
        Config.config['current_prefix'] = data['current_prefix']
        Config.config['moderation_roles_id'] = []
        for mod in data['moderation_roles_id']:
            Config.config['moderation_roles_id'].append(int(mod))
        Config.config['afl_role_id'] = int(data['afl_role_id'])
        Config.config['active_role_id'] = int(data['active']['role_id'])
        Config.config['active_channels_id'] = []
        for channel in data['active']['channels_id']:
            Config.config['active_channels_id'].append(int(channel))
        Config.config['active_threshold'] = data['active']['threshold']
        Config.config['active_duration'] = data['active']['duration']
        Config.config['exceptional_channels_id'] = []
        for channel in data['exceptional_channels_id']:
            Config.config['exceptional_channels_id'].append(int(channel))
        Config.config['poll_channel_id'] = int(data['poll_channel_id'])
        Config.config['under_surveillance_id'] = int(data['under_surveillance_id'])
        Config.config['violations_reset_days'] = data['violations_reset_days']
        Config.config['nick_change_days'] = data['nick_change_days']
        Config.config['greetings'] = data['greetings']

def update_json_file(data, json_file: str) -> None:
    """Scrive su file json i dati passati.

    :param data: i dati da scrivere sul json
    :param json_file: il nome del file da aprire (es. config.json)
    """
    with open(json_file, 'w') as file:
        json.dump(data, file, indent=4)

def get_extensions() -> List[str]:
    """Carica le estensioni dal file extensions.json. Si aspetta di trovare una lista con
    i nomi delle estensioni da aggiungere al bot. Se non trova il file o ci sono errori ritorna
    una lista vuota.

    :returns: la lista coi nomi delle estensioni
    :rtype: List[str]
    """
    try:
        with open('extensions.json', 'r') as file:
            extensions = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        print('nessuna estensione trovata, controlla file extensions.json')
        extensions = []
    return extensions

def count_messages(item: dict) -> int:
    """Ritorna il conteggio totale dei messaggi dei 7 giorni precedenti, ovvero il campo
    counter + tutti gli altri giorni salvati escluso il giorno corrente.

    :param item: dizionario proveniente dal file aflers.json di cui occorre contare i messaggi

    :returns: il conteggio dei messaggi
    :rtype: int
    """
    count = 0
    for i in weekdays:
        if i != datetime.today().weekday():
            count += item[weekdays.get(i)]
    count += item["counter"]
    return count

def count_consolidated_messages(item: dict) -> int:
    """Ritorna il conteggio dei messaggi salvati nei campi mon, tue, wed, ... non include counter
    Lo scopo è contare i messaggi che sono stati consolidati nello storico ai fini di stabilire se
    si è raggiunta la soglia dell'attivo.

    :param item: dizionario proveniente dal file aflers.json di cui occorre contare i messaggi

    :returns: il conteggio dei messaggi
    :rtype: int
    """
    count = 0
    for i in weekdays:
        count += item[weekdays.get(i)]
    return count

def clean(item: dict) -> None:
    """Si occupa di controllare il campo last_message_date e sistemare di conseguenza il
    conteggio dei singoli giorni.

    :param item: dizionario proveniente dal file aflers.json di cui occorre contare i messaggi
    """
    if (item["last_message_date"] is None) or (item["last_message_date"] == datetime.date(datetime.now()).__str__()):
        #(None) tecnicamente previsto da add_warn se uno viene warnato senza aver mai scritto
        #(Oggi) vuol dire che il bot è stato riavviato a metà giornata non devo toccare i contatori
        return
    elif item["last_message_date"] == datetime.date(datetime.today() - timedelta(days=1)).__str__():
        #messaggio di ieri, devo salvare il counter nel giorno corrispondente
        if item["counter"] != 0:
            day = weekdays[datetime.date(datetime.today() - timedelta(days=1)).weekday()]
            item[day] = item["counter"]
            item["counter"] = 0
    else:
        #devo azzerare tutti i giorni della settimana tra la data segnata (esclusa) e oggi (incluso)
        #in teoria potrei anche eliminare solo il giorno precedente contando sul fatto che venga
        #eseguito tutti i giorni ma preferisco azzerare tutti in caso di downtime di qualche giorno
        if item["counter"] != 0:
            day = weekdays[datetime.date(datetime.strptime(item["last_message_date"], '%Y-%m-%d')).weekday()]
            item[day] = item["counter"]
            item["counter"] = 0
        last_day = datetime.date(datetime.strptime(item["last_message_date"], '%Y-%m-%d')).weekday()
        today = datetime.today().weekday()
        while last_day != today:
            last_day += 1
            if last_day > 6:
                last_day = 0
            item[weekdays[last_day]] = 0

def link_to_clean(message: str) -> str:
    """Controlla se il messaggio è un link da accorciare. In tal caso ritorna il link accorciato
    altrimenti None.

    Supporto per ora:
    - link prodotti amazon

    :param message: da controllare
    :returns: None o il link stesso accorciato
    :rtype: str
    """
    cleaned_link = None
    words = message.strip()
    words = message.split(' ')
    if len(words) == 1:   #il messaggio non ha spazi, potrebbe essere un link
        word = words[0]
        #si potrebbe fare una regex visto che sembra che i prodotti abbiano tutti la stessa struttura
        #     amazon.com/nome_lungo_descrittivo/dp/10CARATTER
        if word.__contains__("www.amazon.it") or word.__contains__("www.amazon.com"):
            #logica: tutto quello dopo l'ultimo '/' non serve
            url = word.split('/')
            if len(url[-1]) != 10:  #codice prodotto ha 10 char
                del url[-1]
                del url[0]  #rimuove https:, lo riaggiungo a mano
                cleaned_link = '/'.join(url)
                cleaned_link = 'https:/' + cleaned_link
    return cleaned_link
