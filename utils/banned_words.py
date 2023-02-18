import re
import json
from typing import List


class BannedWords():
    """Gestione delle parole bannate. In particolare si occupa di caricare la lista dal rispettivo
    file banned_words.json che si aspetta di trovare nella stessa cartella del bot. L'elenco è
    salvato in un attributo di classe e tutti i metodi sono statici. Non è fornito un metodo
    __init__ poichè non ci si aspetta che questa classe debba essere istanziata, occorre
    sfruttare metodi e attributi di classe.

    Attributes
    -------------
    banned_words: `list[str]`   attributo di classe contenente l'elenco delle parole bannate

    Methods
    -------------
    load():                         carica dal file banned_words.json l'elenco della parole bannate
    add(word):                      aggiunge la parola all'elenco
    remove(word):                   rimuove la parola dall'elenco
    contains_banned_words(text):    controlla se sono presenti parole bannate nel testo fornito
    """

    banned_words: List[str] = []

    @staticmethod
    def to_string() -> str:
        """Rappresentazione dell'attributo banned_words come stringa. Fatto così invece
        che con __repr__ o __str__ perchè la classe non viene istanziata.

        :returns: la stringa con tutte le parole bannate
        :rtype: str
        """
        string: str = ''
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
            with open('banned_words.json', 'r') as file:
                BannedWords.banned_words = json.load(file)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            with open('banned_words.json', 'w+') as file:
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
        text_to_check: str = text.lower()
        text_to_check = re.sub('0', 'o', text_to_check)
        text_to_check = re.sub('1', 'i', text_to_check)
        text_to_check = re.sub('5', 's', text_to_check)
        text_to_check = re.sub('2', 'z', text_to_check)
        text_to_check = re.sub('8', 'b', text_to_check)
        text_to_check = re.sub('4', 'a', text_to_check)
        text_to_check = re.sub('3', 'e', text_to_check)
        text_to_check = re.sub('7', 't', text_to_check)
        text_to_check = re.sub('9', 'g', text_to_check)
        for word in BannedWords.banned_words:
            regex_word = r'+ *\W*'.join(word)
            match = re.search(regex_word, text_to_check)
            if match is not None:
                return True
        return False
