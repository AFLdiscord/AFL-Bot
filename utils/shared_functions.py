"""Funzionalità condivise tra i diversi file per facilitare la manutenzione.

- update_json_file  salva in json le modifiche
- get_extensions    carica la lista delle estensioni
- link_to_clean     "ripulisce" i link
- evaluate_diff     valuta le differenze tra due messaggi
- discord_tag       verifica se il testo sia un tag discord
- relevant_message  stabilisce se analizzare un messaggio o meno
"""
from difflib import SequenceMatcher
import json
import re
from typing import List, Optional

import discord
from discord.utils import MISSING


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
    extensions: List[str]
    try:
        with open('extensions.json', 'r') as file:
            extensions = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        print('nessuna estensione trovata, controlla file extensions.json')
        extensions = []
    return extensions


def link_to_clean(message: str) -> Optional[str]:
    """Controlla se il messaggio è un link da accorciare. In tal caso ritorna il link accorciato
    altrimenti None.

    Supporto per ora:
    - link prodotti amazon

    :param message: da controllare
    :returns: None o il link stesso accorciato
    :rtype: str
    """
    cleaned_link: Optional[str] = None
    words = message.strip()
    words = message.split(' ')
    if len(words) == 1:   # il messaggio non ha spazi, potrebbe essere un link
        word = words[0]
        if word.__contains__('www.amazon'):
            # si assume che i link ai prodotti amazon abbiano tutti la stessa struttura:
            #     https://amazon.identificativo_nazione_o_com/nome_lungo_descrittivo/dp/10CARATTER
            # la regex effettua l'estrazione di questa porzione di link
            cleaned_link = re.findall(
                r'https:\/\/www\.amazon\..*\/.*\/[A-Z0-9]{10}', word)[0]
    return cleaned_link


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
    if message.guild != _guild or message.author.bot:
        # ignora i messaggi al di fuori dal server o di un bot
        return False
    return True
