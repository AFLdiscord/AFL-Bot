"""Questo script non fa parte del bot ma serve per manipolare
l'archivio aflers.json in caso servisse aggiungere dei campi a
ogni entry e inizializzarli a un valore di default.
Per il momento è pensato per essere un componente indipendente
in futuro potrebbe essere integrato direttamente nel bot e usabile
tramite comandi
"""

import json
from typing import Optional
from shared_functions import update_json_file

class JsonManipulator():
    """Classe per manipolare il contenuto del file.

    Attributes
    -------------
    old_archive: dict, archivio originale caricato dal file
    new_archive: dict, archivio modificato

    Methods
    -------------
    add_and_initialize_field(field_name, default_value) aggiunge nuovo campo e lo inizializza
    save() salva le modifiche nel file aflers
    discard() cancella tutte le modifiche fatte
    print_changes() stampa il nuovo archivio con le modifiche
    """
    def __init__(self) -> None:
        self.file_name = '../aflers.json'
        self.old_archive = {}
        self.new_archive = {}
        self._load()
        self.new_archive = self.old_archive

    def _load(self) -> None:
        try:
            with open(self.file_name,'r') as file:
                self.old_archive = json.load(file)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            raise Exception("Impossibile trovare il file")

    def add_and_initialize_field(self, field_name: str, default_value: Optional[str]=None) -> None:
        """Aggiunge a ogni entry il nuovo campo `field_name` e lo inizializza
        al valore passato `default_value` che può essere anche None.

        :param field_name: nome del campo da aggiungere
        :param default_value: valore di inizializzazione
        """
        for afler in self.new_archive.values():
            if field_name in afler:
                print("Campo già presente")
                break
            afler[field_name] = default_value

    def save(self) -> None:
        """Sovrascrive il vecchio file aflers.json con le modifiche fatte."""
        with open('../aflers.json','w') as file:
            update_json_file(self.new_archive, self.file_name)

    def discard(self) -> None:
        """Annulla le modifiche fatte finora sul nuovo archivio."""
        self.new_archive = self.old_archive

    def print_changes(self) -> None:
        """Stampa l'archivio modificato"""
        print(self.new_archive)

def add(archive: JsonManipulator):
    """Chiede in input il nome del nuovo campo e il valore di default."""
    field_name = input("Nome campo: ")
    default_value = input("Valore di default: ")
    if default_value.lower() == 'none':
        default_value = None
    archive.add_and_initialize_field(field_name, default_value)
    print('Nuovo campo aggiunto')

def save(archive: JsonManipulator):
    archive.save()
    print('Modifiche salvate correttamente.')

def discard(archive: JsonManipulator):
    archive.discard()
    print('Scartate tutte le modifiche')

def print_changes(archive: JsonManipulator):
    archive.print_changes()

def end(archive: JsonManipulator):
    archive.save()
    exit(0)

def main():
    try:
        archive = JsonManipulator()
    except Exception as e:
        print(e)
        exit(-1)
    print('Archivio caricato.')
    commands = {
        1 : add,
        2 : save,
        3 : discard,
        4 : print_changes,
        5 : end
    }
    while(True):
        selection = int(input('''Inserisci il numero corrispondente
            1 : add  aggiunge un campo all'archivio
            2 : save  salva le modifiche
            3 : discard  cancella le modifiche
            4 : print  stampa il file con le modifiche fatte
            5 : end  salva ed esce
        '''))
        if selection in commands:
            commands[selection](archive)

if __name__ == '__main__':
    main()