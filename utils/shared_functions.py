"""Funzionalità condivise tra i diversi file per facilitare la manutenzione.

- update_json_file  salva in json le modifiche
- get_extensions    carica la lista delle estensioni
- clean_links     "ripulisce" i link
- evaluate_diff     valuta le differenze tra due messaggi
- discord_tag       verifica se il testo sia un tag discord
- relevant_message  stabilisce se analizzare un messaggio o meno
- next_datetime     restituisce la data corretta
"""
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import json
from typing import List, Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import requests

import discord
from discord.utils import MISSING


def update_json_file(data, json_file: str) -> None:
    """Scrive su file json i dati passati.
    Se il file non esiste, lo crea.

    :param data: i dati da scrivere sul json
    :param json_file: il nome del file da aprire (es. config.json)
    """
    with open(json_file, 'w+') as file:
        json.dump(data, file, indent=4, default=str)


def get_extensions() -> List[str]:
    """Carica le estensioni dal file extensions.json. Si aspetta di trovare una lista con
    i nomi delle estensioni da aggiungere al bot. Se non trova il file o ci sono errori ritorna
    una lista vuota.

    :returns: la lista coi nomi delle estensioni
    :rtype: List[str]
    """
    extensions: List[str]
    try:
        with open('extensions.json', 'r') as file:
            extensions = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        print('nessuna estensione trovata, controlla file extensions.json')
        extensions = []
    return extensions


def clean_links(message: str) -> str:
    """Controlla se il messaggio ha dei link da accorciare e in caso positivo li accorcia.
    Se non c'è nessun link da accorciare, il messaggio rimane intatto.

    Supporto per ora:
    - link prodotti amazon
    - link youtube

    :param message: da controllare
    :returns: il messaggio, con eventuali link ripuliti
    :rtype: str
    """
    cleaned_link: Optional[str] = None
    words = message.strip().split(' ')
    for i, word in enumerate(words):
        parsing = urlparse(word)
        netloc = parsing.netloc
        if netloc == 'amzn.eu':
            cleaned_link = requests.get(word).url
        elif (netloc.endswith('.amazon.com') or netloc.endswith('.amazon.it') or
              netloc == 'amazon.com' or netloc == 'amazon.it'):
            parsing = parsing._replace(params='', query='')
            cleaned_link = urlunparse(parsing)
        elif (netloc.endswith('.youtube.com') or netloc.endswith('.youtu.be') or
              netloc == 'youtube.com' or netloc == 'youtu.be'):
            query = parse_qs(parsing.query)
            try:
                del query['si']
            except KeyError:
                continue
            query = urlencode(query, doseq=True)
            parsing = parsing._replace(query=query)
            cleaned_link = urlunparse(parsing)
        if cleaned_link is not None:
            words[i] = cleaned_link
            cleaned_link = None
    return ' '.join(words)


class TypedMatcher(SequenceMatcher):
    """Serve soltanto per aggiungere il typing agli attributi :("""

    def __init__(self, before: str, after: str):
        super().__init__(None, before, after)
        self.a: str
        self.b: str


def evaluate_diff(before: str, after: str) -> str:
    """Confronta due stringhe e restituisce una stringa formattata
    che evidenzia le differenze tra le due.

    :param before: la stringa di partenza
    :param after: la stringa modificata

    :returns: una stringa formattata per evidenziare le modifiche
    :rtype: str
    """
    diff = TypedMatcher(before, after)
    output: list[str] = []
    for opcode, a0, a1, b0, b1 in diff.get_opcodes():
        if opcode == 'equal':
            output.append(diff.a[a0:a1])
        elif opcode == 'insert':
            output.append(f'**{diff.b[b0:b1]}**')
        elif opcode == 'delete':
            output.append(f'~~{diff.a[a0:a1]}~~')
        elif opcode == 'replace':
            output.append(f'~~{diff.a[a0:a1]}~~**{diff.b[b0:b1]}**')
        else:
            return f'Before:\n    {before}\nAfter:\n    {after}'
    return ''.join(output)


def discord_tag(content: str) -> bool:
    """Controlla se la stringa riconosciuta come comando è un tag di discord.
    Gestisce i conflitti nel caso in cui il prefisso del bot sia settato a '<'.

    I markdown di discord sono raggruppabili nelle seguenti categorie:
    <@id> -> menzione membri o ruoli
    <#id> -> menzione canali
    <:id> -> emoji personalizzate
    <a:id> -> emoji animate
    <t:timestamp> -> timestamp
    Inoltre, viene gestita l'emoticon '<3', che non viene convertita automaticamente
    nell'emoji standard quando il messaggio è inviato dal client mobile.

    :param content: comando che ha dato errore

    :returns: se rappresenta un markdown
    :rtype: bool
    """
    return content[1] in ('@', '#', ':', 'a', 't', '3')


_guild: discord.Guild = MISSING


def relevant_message(message: discord.Message) -> bool:
    """Controlla se il messaggio è da processare o meno

    :param message: messaggio da controllare
    :returns: True se va processato, False altrimenti
    :rtype: bool
    """
    global _guild
    if message.author.bot:
        return False
    if message.type not in (discord.MessageType.default, discord.MessageType.reply):
        # ignora i messaggi "di sistema" tipo creazione thread (vedi #59), pin, etc che sono generati
        # automaticamente ma vengono attribuiti all'utente che esegue l'azione
        return False
    if _guild is MISSING:
        # workaround per evitare una dipendenza circolare con Config, lo
        # giustifico poiché serve soltanto la guild ed è improbabile che
        # venga sostituita a runtime
        from utils.config import Config
        _guild = Config.get_config().guild
        del Config
    if message.guild != _guild:
        # ignora i messaggi al di fuori dal server
        return False
    return True


def next_datetime(start_date: datetime, days: int) -> datetime:
    """Restituisce il prossimo datetime, prestando attenzione al possibile
    cambiamento di DST

    :param start_date: la data di partenza
    :param days: la distanza in giorni
    :returns: il datetime con lo stesso orario
    :rtype: datetime.datetime
    """
    start_date = start_date.astimezone()
    start_date = start_date.replace(tzinfo=None)
    next_date = start_date + timedelta(days=days)
    return next_date.astimezone()
