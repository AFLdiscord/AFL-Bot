"""Questo script non fa parte del bot ma serve per manipolare
l'archivio aflers.json in caso servisse aggiungere o rimuovere dei campi.
Per il momento è pensato per essere un componente indipendente
in futuro potrebbe essere integrato direttamente nel bot e usabile
tramite comandi.
"""

import json
import os
from copy import deepcopy
from typing import Optional, Union
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
    delete_field(field_name)  rimuove un campo dall'archivio
    save() salva le modifiche nel file aflers
    discard() cancella tutte le modifiche fatte
    print_changes() stampa il nuovo archivio con le modifiche
    """

    def __init__(self) -> None:
        self.file_name = 'aflers.json'
        self.backup_old = 'aflers.json.old'
        self.fields = 'utils/fields.json'
        self.fields_list = []
        self.old_fields_list = []
        self.old_archive = {}
        self.new_archive = {}
        self._load()
        self.new_archive = deepcopy(self.old_archive)

    def _load(self) -> None:
        try:
            with open(self.file_name, 'r') as file:
                self.old_archive = json.load(file)
            with open(os.path.join(os.getcwd(), self.fields), 'r') as file:
                self.fields_list = json.load(file)
            self.old_fields_list.extend(self.fields_list)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            raise Exception("Impossibile trovare il file")

    def add_and_initialize_field(self, field_name: str, default_value: str) -> bool:
        """Aggiunge a ogni entry il nuovo campo `field_name` e lo inizializza
        al valore passato `default_value` che può essere anche None.

        :param field_name: nome del campo da aggiungere
        :param default_value: valore di inizializzazione
        :returns: se il campo è stato aggiunto
        :rtype: bool
        """
        value: Optional[Union[str, bool, int]] = None
        if field_name in self.fields_list:
            return False
        if default_value != "":
            if default_value.isdecimal():
                value = int(default_value)
            else:
                default_value_casefold = default_value.casefold()
                if default_value_casefold == 'true'.casefold():
                    value = True
                elif default_value_casefold == 'false'.casefold():
                    value = False
        for afler in self.new_archive.values():
            if field_name in afler:
                return False
            afler[field_name] = value
        self.fields_list.append(field_name)
        return True

    def delete_field(self, field_name: str) -> bool:
        """Rimuove un campo da tutte le entry del file. Se non esiste
        non fa nulla e ritorna falso.

        :returns:  se il campo è stato rimosso
        :rtype: bool
        """
        for afler in self.new_archive.values():
            if field_name not in afler:
                return False
            del afler[field_name]
        self.fields_list.remove(field_name)
        return True

    def save(self) -> None:
        """Sovrascrive il vecchio file aflers.json con le modifiche fatte.
        Il vecchio archivio viene salvato in afler.json.old
        """
        #with open(self.file_name, 'w') as file:
        update_json_file(self.new_archive, self.file_name)
        #with open(self.backup_old, 'w') as file:
        update_json_file(self.old_archive, self.backup_old)
        #with open(self.fields, 'w') as file:
        update_json_file(self.fields_list, self.fields)

    def discard(self) -> None:
        """Annulla le modifiche fatte finora sul nuovo archivio."""
        self.new_archive = deepcopy(self.old_archive)
        self.fields_list = deepcopy(self.old_fields_list)

    def print_changes(self) -> None:
        """Stampa una entry dell'archivio per osservare le modifiche."""
        sample_entry = self.new_archive[list(self.new_archive)[0]]
        for key in sample_entry:
            print(f'{key} : {sample_entry[key]}')

    def check_integrity(self) -> bool:
        """Controlla che tutte le entry nel file abbiano tutti i campi. L'elenco dei campi è
        contenuto nel file fields.json.
        Utile per verificare di non fare casino in caso di modifiche veloci a mano del file.
        L'esito viene stamapato a video, specificando i campi sbagliati in caso di errori e
        ritorna un booleano per indicare se il file è coerente o meno.
        """
        correct = True
        fields_set = set(self.fields_list)
        for key in self.old_archive:
            entry = set(self.old_archive[key].keys())
            missing_fields = fields_set.difference(entry)
            extra_fields = entry.difference(fields_set)
            print(f'Entry {key}')
            if len(missing_fields) != 0:
                print(f'Campi mancanti {missing_fields}')
                correct = False
            if len(extra_fields) != 0:
                print(f'Campi extra: {extra_fields}')
                correct = False
            if len(extra_fields) == 0 and len(missing_fields) == 0:
                print(f'Nessun errore con l\'entry {key}')
            missing_fields = set()
            extra_fields = set()
        return correct


def add(archive: JsonManipulator) -> None:
    """Chiede in input il nome del nuovo campo e il valore di default."""
    field_name = input("Nome campo: ")
    default_value = input("Valore di default (invio per \"null\"): ")
    if archive.add_and_initialize_field(field_name, default_value):
        print('Nuovo campo aggiunto.')
    else:
        print('Campo già esistente.')


def delete(archive: JsonManipulator) -> None:
    """Chiede in input il nome del campo da cancellare"""
    field_name = input("Nome campo: ")
    if archive.delete_field(field_name):
        print('Campo eliminato.')
    else:
        print('Il campo passato non esiste.')


def save(archive: JsonManipulator) -> None:
    archive.save()
    print('Modifiche salvate correttamente.')


def discard(archive: JsonManipulator) -> None:
    archive.discard()
    print('Scartate tutte le modifiche.')


def print_changes(archive: JsonManipulator) -> None:
    archive.print_changes()


def check_integrity(archive: JsonManipulator) -> None:
    if(archive.check_integrity()):
        print('Non sono stati rilevati errori nell\'archivio.')


def save_and_exit(archive: JsonManipulator) -> None:
    archive.save()
    exit(0)


def discard_and_exit(archive: JsonManipulator) -> None:
    archive.discard()
    exit(0)


def main():
    try:
        archive = JsonManipulator()
    except Exception as e:
        print(e)
        exit(-1)
    print('Archivio caricato.')
    commands = {
        1: add,
        2: delete,
        3: save,
        4: discard,
        5: print_changes,
        6: check_integrity,
        7: save_and_exit,
        8: discard_and_exit
    }
    while(True):
        selection = input('''Inserisci il numero corrispondente
            1 : add  aggiunge un campo all'archivio
            2 : delete  cancella un campo dall'archivio
            3 : save  salva le modifiche
            4 : discard  cancella le modifiche
            5 : print  stampa il file con le modifiche fatte
            6 : check  stampa a video se ci sono incongruenze nel file
            7 : save and exit  salva ed esce
            8 : discard and exit
        ''')
        try:
            selection = int(selection)
        except ValueError as e:
            print('Comando non valido.')
            continue
        if selection in commands:
            commands[selection](archive)
        else:
            print('Comando non valido.')


if __name__ == '__main__':
    main()
