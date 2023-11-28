from __future__ import annotations
from datetime import date
from discord import Embed
import json
from os import rename
from typing import Any, ClassVar, Dict, List

from utils.afler import Afler
from utils.bot_logger import BotLogger
from utils.config import Config
from utils.shared_functions import update_json_file

import discord
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
    _archive: `Archive` attributo di classe, contiene l'istanza dell'archivio

    Classmethods
    -------------
    load_archive():   carica il contenuto del file nell'attributo di classe
    get_instance():   ritorna l'unica istanza dell'archivio

    Methods
    -------------
    get():           ritorna i dati dell'afler richiesto
    add():           aggiunge una nuova entry all'archivio
    remove():        rimuove l'afler dall'archivio
    is_present():    controlla se l'afler è presente o meno
    keys():          ritorna gli id di tutti gli aflers salvati
    values():        ritorna tutte le istanze di afler salvate
    save():          salva le modifiche fatte all'archivio
    contains_nick(): controlla se il nickname è già utilizzato da un afler
    """
    _archive_instance: ClassVar[Archive] = MISSING

    def __init__(self) -> None:
        # è sbagliato creare un'istanza, è un singleton
        self.archive: Dict[int, Afler]
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
        Se chiamato ulteriormente a bot avviato, serve a refreshare
        l'archivio, rileggendo il file.
        """
        archive: Dict[int, Any] = {}
        try:
            with open('aflers.json', 'r') as file:
                raw_archive: Dict[str, Any] = json.load(file)
                # conversione degli id da str a int così come sono su discord
                for k in raw_archive:
                    archive[int(k)] = raw_archive[k]
        except FileNotFoundError:
            pass
        except json.JSONDecodeError:
            print(
                "L'archivio sembra essere corrotto: backup e creazione di un nuovo archivio...")
            rename('aflers.json', f'aflers-backup-{date.today()}.json')
            print(
                f'Il vecchio archivio è stato salvato nel file aflers-backup-{date.today()}.json.')
        finally:
            # Serve creare un'istanza dell'archivio all'avvio.
            # Questo non è il caso invece quando si vuole fare il refresh
            # dell'archivio dopo aver modificato i campi manualmente.
            if cls._archive_instance is MISSING:
                cls._archive_instance = cls.__new__(cls)
            cls._archive_instance.archive = {}
            for key in archive.keys():
                cls._archive_instance.archive[key] = Afler.from_archive(
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
            return self.archive[id]
        except KeyError:
            raise

    def add(self, id: int, afler: Afler) -> None:
        """Aggiunge una nuova entry all'archivio. Se era già presente
        non fa nulla.

        :param afler: afler da aggiungere
        """
        if not self.is_present(id):
            self.archive[id] = afler

    def remove(self, id: int) -> None:
        """Rimuove l'afler dall'archivio. In caso non fosse presente non fa nulla.

        :param id: id dell'afler richiesto
        """
        if self.is_present(id):
            del self.archive[id]

    def is_present(self, id: int) -> bool:
        """Ritorna True se nell'archivio è presente un membro con l'id passato.

        :param id: membro richiesto

        :returns: True se il membro è presente, False altrimenti
        :rtype: bool
        """
        return id in self.archive.keys()

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
        return list(self.archive.values())

    def save(self, filename: str = 'aflers.json') -> None:
        """Salva su disco le modifiche effettuate all'archivio.
        Opzionalmente si può specificare il nome del file, ad esempio se occorre fare una copia

        :param filename: il nome del file su cui salvare (default='aflers.json')

        NOTA: per ora non viene mai chiamato automaticamente dagli altri metodi
        ma deve essere esplicitamente usato quando si vogliono salvare le modifiche.
        L'idea è lasciare più flessibilità, consentendo di effettuare operazioni diverse
        e poi salvare tutto alla fine.
        """
        archive = {id: afler.__dict__ for id, afler in self.archive.items()}
        update_json_file(archive, filename)

    def contains_nick(self, nick: str) -> bool:
        """Controlla se un nickname sia utilizzato correntemente da un afler.

        :param nick: nickname da cercare

        :returns: True se il nickname è utilizzato da un altro membro, False altrimenti
        :rtype: bool
        """
        return any(afler.nick == nick for afler in self.values())

    async def handle_counters(self) -> None:
        """Esegue il controllo dei contatori degli afler.

        Nello specifico si occupa di:
        - consolidare dei messaggi nel buffer oratore se necessario;
        - azzerare dei messaggi conteggiati scaduti;
        - assegnare/rimuovere i ruoli (i mod sono esclusi);
        - rimuovere strike/violazioni scaduti.

        Di norma, viene chiamato durante la task periodica.
        """
        logger = BotLogger.get_instance()
        config = Config.get_config()
        for id, afler in self.archive.items():
            afler.clean_orator_buffer()
            count = afler.count_consolidated_messages()
            member = config.guild.get_member(id)
            assert member is not None
            # controllo messaggi per ruolo attivo
            if (count >= config.orator_threshold and
                    not any(role in config.moderation_roles for role in member.roles)):
                await member.add_roles(config.orator_role)
                if afler.orator:
                    msg = f'{member.mention}: rinnovato ruolo {config.orator_role.mention}'
                else:
                    msg = f'{member.mention} è diventato {config.orator_role.mention}'
                await logger.log(msg)
                await config.main_channel.send(embed=Embed(description=msg))
                afler.set_orator()
            # controllo delle violazioni
            violations_count = afler.reset_violations()
            if violations_count > 0:
                msg = f'rimosse le {violations_count} violazioni di {member.mention}'
                await logger.log(msg)
                # rimozione del ruolo sotto sorveglianza
                if config.surveillance_role in member.roles:
                    await member.remove_roles(config.surveillance_role)
                    await logger.log(f'{member.mention} rimosso da {config.surveillance_role.mention}')
            # rimuovo i messaggi contati 7 giorni fa
            afler.forget_last_week()
            # controllo scadenza ruolo attivo
            if afler.is_orator_expired():
                await member.remove_roles(config.orator_role)
                msg = f'{member.mention} non è più un {config.orator_role.mention}'
                await logger.log(msg)
                await config.main_channel.send(embed=Embed(description=f'{msg} :('))
                afler.remove_orator()
            # controllo scadenza ruolo cazzaro
            if afler.is_dank_expired():
                await member.remove_roles(config.dank_role)
                msg = f'{member.mention} non è più un {config.dank_role.mention}'
                await logger.log(msg)
                await config.main_channel.send(embed=Embed(description=f'{msg} :)'))
                afler.remove_dank()

    async def increase_orator_buffer(self, afler: discord.Member) -> None:
        """Incrementa il buffer oratore dell'afler."""
        item = self.get(afler.id)
        item.increase_orator_buffer()
        self.save()

    async def increase_dank_counter(self, afler: discord.Member) -> None:
        """Incrementa il contatore cazzaro dell'afler, eventualmente
        assegnando il ruolo.
        """
        item = self.get(afler.id)
        item.increase_dank_counter()
        if item.is_eligible_for_dank():
            result = ''
            if item.dank:
                result = f': rinnovato ruolo '
            else:
                result = f' è diventato un '
            msg = f'{afler.mention}{result}{Config.get_config().dank_role.mention}'
            await BotLogger.get_instance().log(msg)
            await Config.get_config().main_channel.send(embed=discord.Embed(description=msg))
            item.set_dank()
            await afler.add_roles(Config.get_config().dank_role)
        self.save()
