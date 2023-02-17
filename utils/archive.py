from __future__ import annotations
from datetime import date
import json
from os import rename
from typing import Any, ClassVar, Dict, List

from utils.afler import Afler
from utils.shared_functions import update_json_file

from discord.utils import MISSING

# archivio con i dati


class Archive():
    """Gestione dell'archivio con i dati riguardo i messaggi inviati.
    L'idea è di tenerlo in memoria invece di aprire il file a ogni modifica. L'interfaccia è
    simile a quella di un dizionario (leggere tutte le chiavi, tutti i valori, etc)
    ma ci sono dei metodi specifici in più per svolgere altre funzioni.

    NOTA: questa classe è pensata per essere un singleton e non va istanziata direttamente
    ma occorre ottenere l'unica istanza tramite l'apposito metodo get_instance.

    Attributes
    -------------
    _archive: Archive   attributo di classe, contiene l'istanza dell'archivio

    Classmethods
    -------------
    load_archive()   carica il contenuto del file nell'attributo di classe
    get_instance()   ritorna l'unica istanza dell'archivio

    Methods
    -------------
    get()           ritorna i dati dell'afler richiesto
    add()           aggiunge una nuova entry all'archivio
    remove()        rimuove l'afler dall'archivio
    is_present()    controlla se l'afler è presente o meno
    keys()          ritorna gli id di tutti gli aflers salvati
    values()        ritorna tutte le istanze di afler salvate
    save()          salva le modifiche fatte all'archivio
    contains_nick() controlla se il nickname è già utilizzato da un afler
    """
    _archive_instance: ClassVar[Archive] = MISSING

    def __init__(self) -> None:
        # è sbagliato creare un'istanza, è un singleton
        self.archive: Dict[int, Any]
        self.wrapped_archive: Dict[int, Afler]
        raise RuntimeError(
            'Non istanziare archivio, usa Archive.get_instance()')

    @classmethod
    def get_instance(cls) -> Archive:
        """Ritorna l'unica istanza dell'archivio."""
        if cls._archive_instance is MISSING:
            cls.load_archive()
        return cls._archive_instance

    @classmethod
    def load_archive(cls):
        """Carica l'archivio da file e lo salva in archive.
        Se non esiste lo crea vuoto. Se chiamato ulteriormente a bot
        avviato, serve a refreshare l'archivio, rileggendo il file.
        """
        archive: Dict[int, Any] = {}
        try:
            with open('aflers.json', 'r') as file:
                raw_archive: Dict[str, Any] = json.load(file)
                # conversione degli id da str a int così come sono su discord
                for k in raw_archive:
                    archive[int(k)] = raw_archive[k]
        except FileNotFoundError:
            file = open('aflers.json', 'x')
            file.close()
        except json.JSONDecodeError:
            with open('aflers.json', 'r') as file:
                first_line = file.readline()
            if len(first_line) >= 1:
                choice = input("L'archivio sembra essere corrotto: creare un nuovo archivio? [Y/n] ").strip()
                if choice.casefold() != 'n':
                    print('Creazione di un nuovo archivio...')
                    rename('aflers.json', f'aflers-backup-{date.today()}.json')
                    file = open('aflers.json', 'x')
                    file.close()
                    print(f'Il vecchio archivio è stato salvato nel file aflers-backup-{date.today()}.json.')
                    print("Dopo averlo corretto, cancella l'archivio attuale e rinomina quello vecchio in 'aflers.json'.")
                else:
                    print("Correggi l'archivio prima di riavviare il bot.")
                    exit()
        finally:
            # Serve creare un'istanza dell'archivio all'avvio.
            # Questo non è il caso invece quando si vuole fare il refresh
            # dell'archivio dopo aver modificato i campi manualmente.
            if cls._archive_instance is MISSING:
                cls._archive_instance = cls.__new__(cls)
            # cls._archive_instance.archive l'archivio in formato dizionario così da poterlo salvare agevolemente
            #
            # cls._archive_instance.wrapped_archive ogni entry dell'archivio è incapsulata nella classe Afler
            # per manipolarla più facilmente
            #
            # nota che i dati dei due attributi sono condivisi, quindi lo stato è sempre aggiornato
            cls._archive_instance.archive = archive
            cls._archive_instance.wrapped_archive = {}
            for key in archive.keys():
                cls._archive_instance.wrapped_archive[key] = Afler.from_archive(
                    archive[key])

    @classmethod
    def refresh(cls):
        """Sovrascrive il contenuto dell'archivio con i dati presenti nel file
        'aflers.json'.
        Prima di fare ciò salva una copia dell'archivio corrente in 'aflers.json.old'.
        """
        cls._archive_instance.save(filename='aflers.json.old')
        cls.load_archive()

    def get(self, id: int) -> Afler:
        """Recupera i dati dell'afler dato il suo id.

        :param id: id dell'afler richiesto

        :returns: i dati dell'afler richiesto
        :rtype:  Afler

        :raises: KeyError se l'afler non è presente nell'archivio
        """
        try:
            return self.wrapped_archive[id]
        except KeyError:
            raise

    def add(self, id: int, afler: Afler) -> None:
        """Aggiunge una nuova entry all'archivio. Se era già presente
        non fa nulla.

        :param afler: afler da aggiungere
        """
        if not self.is_present(id):
            self.archive[id] = afler.data
            self.wrapped_archive[id] = afler

    def remove(self, id: int) -> None:
        """Rimuove l'afler dall'archivio. In caso non fosse presente non fa nulla.

        :param id: id dell'afler richiesto
        """
        if self.is_present(id):
            del self.wrapped_archive[id]
            del self.archive[id]

    def is_present(self, id: int) -> bool:
        """Ritorna True se nell'archivio è presente un membro con l'id passato.

        :param id: membro richiesto

        :returns: True se il membro è presente, False altrimenti
        :rtype: bool
        """
        if id in self.archive.keys() and id in self.wrapped_archive.keys():
            return True
        else:
            return False

    def keys(self) -> List[int]:
        """Ritorna una lista con gli id di tutti gli aflers presenti nell'archivio.
        Pensato per essere usato come il metodo keys() di un dizionario

        :returns: lista con tutti gli id
        :rtype: List[int]
        """
        return list(self.archive.keys())

    def values(self) -> List[Afler]:
        """Ritorna una lista con tutti i dati degli aflers salvati nell'archivio.
        Pensato per essere usato come il metodo values() di un dizionario

        :returns: lista con tutti gli afler
        :rtype: List[Afler]
        """
        return list(self.wrapped_archive.values())

    def save(self, filename: str = 'aflers.json') -> None:
        """Salva su disco le modifiche effettuate all'archivio.
        Opzionalmente si può specificare il nome del file, ad esempio se occorre fare una copia

        :param filename: il nome del file su cui salvare (default='aflers.json')

        NOTA: per ora non viene mai chiamato automaticamente dagli altri metodi
        ma deve essere esplicitamente usato quando si vogliono salvare le modifiche.
        L'idea è lasciare più flessibilità, consentendo di effettuare operazioni diverse
        e poi salvare tutto alla fine.
        """
        update_json_file(self.archive, filename)

    def contains_nick(self, nick: str) -> bool:
        """Controlla se un nickname sia utilizzato correntemente da un afler.

        :param nick: nickname da cercare

        :returns: True se il nickname è utilizzato da un altro membro, False altrimenti
        :rtype: bool
        """
        return any(afler.nick == nick for afler in self.values())
