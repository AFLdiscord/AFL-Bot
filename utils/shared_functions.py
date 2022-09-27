from __future__ import annotations
"""Funzionalità condivise tra le diverse cog per facilitare la manutenzione. In particolare:
Classi:
- Afler per eseguire operazioni sugli elementi dell' archivio
- Archive archivio con i dati
- BannedWords per gestione delle parole bannate
- Config per la gestione dei parametri di configuarazione del bot

Funzioni:
- update_json_file per salvare in json le modifiche
- get_extensions per caricare la lista delle estensioni
- link_to_clean per "ripulire" i link
"""

import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, ClassVar, Dict, List, Optional, Union, TypedDict

import discord
from discord.ext import commands

# utile per passare dal giorno della settimana restituito da weekday() direttamente
# al campo corrispondente nel dizionario del json
weekdays: Dict[int, str] = {
    0: 'mon',
    1: 'tue',
    2: 'wed',
    3: 'thu',
    4: 'fri',
    5: 'sat',
    6: 'sun'
}

# wrapper per eseguire operazioni sugli elementi dell' archivio, ossia gli aflers


class Afler():
    """Rappresentazione di un membro del server.
    Semplifica le operazioni di lettura/scrittura quando si accede all'archivio.
    È importante implementare questa classe tenendo separata la logica di gestione del bot
    dalla logica di gestione dei dati degli afler.
    Esempio: non controllare la soglia dei messaggi qua ma passare il totale all'esterno dove viene
    fatto il controllo in base alla config del bot

    Attributes
    -------------
    data: Dict[]                            contiene i dati dell'afler
    nick: str                               contiene il nickname dell'afler
    bio: str                                contiene la bio dell'afler
    orator: bool                            flag per dire se è oratore o meno
    dank: bool                              flag per dire se è cazzaro o meno
    dank_messages_buffer: int               messaggi del ruolo cazzaro inviati nella finestra di tempo
    orator_total_messages: int              totale messaggi orator
    dank_total_messages: int                totale messaggi dank
    total_messages: int                     messaggi totali inviati dall'afler
    orator_expiration: Optional[date]       data di scadenza del ruolo oratore
    dank_expiration: Optional[date]         data di scadenza del ruolo cazzaro
    last_nick_change: date                  data dell'ultimo cambio nickname
    last_message_date: Optional[date]       data dell'ultimo messaggio valido per l'oratore
    last_violations_count: Optional[date]   data di ultima violazione

    Classmethods
    -------------
    new_entry(nick) crea un nuovo afler
    from_archive(data) crea un afler con i dati letti dall'archivio

    Methods
    -------------
    increase_orator_counter() incrementa il contatore oratore
    decrease_orator_counter() decrementa il contatore oratore del giorno corrente
    set_orator() imposta l'afler come oratore
    is_orator_expired() controlla se il ruolo oratore è scaduto
    remove_orator() rimuove il ruolo oratore
    set_dank() imposta l'afler come cazzaro
    increase_dank_counter() incrementa il contatore cazzaro
    decrease_dank_counter() decrementa il contatore cazzaro
    is_eligible_for_dank() controlla se l'afler può ottenere il ruolo cazzaro
    is_dank_expired() controlla se il ruolo cazzaro è scaduto
    remove_dank() rimuove il ruolo cazzaro
    modify_warn() aggiunge o rimuove warn all'afler
    warn_count() ritorna il numero di warn
    reset_violations() azzera il numero di violazioni commesse
    forget_last_week() azzera il contatore corrispondente a 7 giorni fa
    clean() sistema i dati salvati al cambio di giorno
    count_orator_messages() conta i messaggi totali
    count_consolidated_messages() conta solo i messaggi dei giorni precedenti a oggi
    """

    def __init__(self, data: Dict[str, Any]) -> None:
        """
        :param data: dizionario che contiene i dati dell'afler
        """
        self.data = data

    @classmethod
    def new_entry(cls, nickname: str) -> Afler:
        """Crea un nuovo afler.

        :param nickname: il nickname del nuovo afler

        :returns: l'afler appena creato
        :rtype: Afler
        """
        return cls({
            'nick': nickname,
            'last_nick_change': date.today().isoformat(),
            # TODO valutare di snellire il dizionario
            'mon': 0,
            'tue': 0,
            'wed': 0,
            'thu': 0,
            'fri': 0,
            'sat': 0,
            'sun': 0,
            'counter': 0,
            'last_message_date': None,
            'violations_count': 0,
            'last_violation_count': None,
            'orator': False,
            'orator_expiration': None,
            'orator_total_messages': 0,
            'dank': False,
            'dank_messages_buffer': 0,
            'dank_first_message_timestamp': None,
            'dank_expiration': None,
            'dank_total_messages': 0,
            'bio': None
        })

    @classmethod
    def from_archive(cls, afler_data: Dict[str, Any]) -> Afler:
        """Restituisce un afler con i valori letti dall'archivio.

        :param afler_data: i dati dell'afler letti dall'archivio

        :returns: l'afler caricato
        :rtype: Afler
        """
        return cls(afler_data)

    @property
    def nick(self) -> str:
        """Restituisce il nickname dell'afler.

        :returns: il nickname dell'afler
        :rtype: str
        """
        return self.data['nick']

    @nick.setter
    def nick(self, new_nick: str) -> None:
        """Modifica il nome dell'afler.

        :param new_nick: nuovo nickname
        """
        self.data['nick'] = new_nick
        self.data['last_nick_change'] = datetime.date(datetime.now()).__str__()

    @property
    def bio(self) -> str:
        """Restituisce la bio dell'afler.

        :returns: bio dell'afler
        :rtype: str
        """
        return self.data['bio']

    @bio.setter
    def bio(self, bio: str) -> None:
        """Imposta la bio dell'afler.

        :param bio: la stringa con la bio
        """
        self.data['bio'] = bio

    @property
    def orator(self) -> bool:
        """Ritorna lo stato oratore dell'afler.

        :returns: True se oratore, False altrimenti
        :rtype: bool
        """
        return self.data['orator']

    @property
    def dank(self) -> bool:
        """Ritorna lo stato cazzaro dell'afler.

        :returns: True se cazzaro, False altrimenti
        :rtype: bool
        """
        return self.data['dank']

    @property
    def dank_messages_buffer(self) -> int:
        """Ritorna il numero di messaggi nel buffer cazzaro.

        :return: il numero di messaggi nel buffer cazzaro
        :rtype: int
        """
        return self.data['dank_messages_buffer']

    @property
    def orator_total_messages(self) -> int:
        """Ritorna il numero totale di messaggi orator.
        I totali sono calcolati dalla versione 2.0 del bot.
        
        :return: il totale dei messaggi orator
        :rtype: int
        """
        return self.data['orator_total_messages']

    @property
    def dank_total_messages(self) -> int:
        """Ritorna il numero totale di messaggi dank.
        I totali sono calcolati dalla versione 2.0 del bot.
        
        :return: il totale dei messaggi dank
        :rtype: int
        """
        return self.data['dank_total_messages']

    @property
    def total_messages(self) -> int:
        """Restituisce il numero totale di messaggi inviati dall'afler.
        I totali sono calcolati dalla versione 2.0 del bot.

        :return: il numero totale di messaggi mandati
        :rtype: int
        """
        return self.data['orator_total_messages'] + self.data['dank_total_messages']

    @property
    def orator_expiration(self) -> Optional[date]:
        """Ritorna la data di scadenza del ruolo oratore.

        :returns: data di scadenza oratore
        :rtype: Optional[datetime.date]
        """
        if self.data['orator_expiration'] is not None:
            return date.fromisoformat(self.data['orator_expiration'])
        else:
            return None

    @property
    def dank_expiration(self) -> Optional[date]:
        """Ritorna la data di scadenza del ruolo cazzaro.

        :returns: data di scadenza cazzaro
        :rtype: Optional[datetime.date]
        """
        if self.data['dank_expiration'] is not None:
            return datetime.fromisoformat(self.data['dank_expiration'])
        else:
            return None

    @property
    def last_nick_change(self) -> date:
        """Ritorna la data dell'utlimo cambio di nickname

        :returns: data ultimo cambio
        :rtype: datetime.date
        """
        return datetime.date(datetime.strptime(self.data['last_nick_change'], '%Y-%m-%d'))

    @property
    def last_message_date(self) -> Optional[date]:
        """Ritorna la data dell'ultimo messaggio valido per il conteggio dell'oratore.

        :returns: data ultimo messaggio
        :rtype: Optional[datetime.date]
        """
        if self.data['last_message_date'] is not None:
            return datetime.date(datetime.strptime(self.data['last_message_date'], '%Y-%m-%d'))
        else:
            return None

    @property
    def last_violations_count(self) -> Optional[date]:
        """Ritorna la data dell'ultima violazione.

        :returns: data ultima violazione
        :rtype: Optional[datetime.date]
        """
        if self.data['last_violation_count'] is not None:
            return datetime.date(datetime.strptime(self.data['last_violation_count'], '%Y-%m-%d'))
        else:
            return None

    def increase_orator_counter(self) -> None:
        """Aggiorna il contatore oratore dell'utente autore del messaggio passato. In caso l'utente non sia
        presente nel file aflers.json lo aggiunge inizializzando tutti i contatori dei giorni a 0 e counter a 1.
        Si occupa anche di aggiornare il campo 'last_message_date'.
        """
        if self.data['last_message_date'] == datetime.date(datetime.now()).__str__():
            # messaggi dello stesso giorno, continuo a contare
            self.data['counter'] += 1
        elif self.data['last_message_date'] is None:
            # primo messaggio della persona
            self.data['counter'] = 1
            self.data['last_message_date'] = datetime.date(
                datetime.now()).__str__()
        else:
            # è finito il giorno, salva i messaggi di 'counter' nel
            # giorno corrispondente e aggiorna data ultimo messaggio
            if self.data['counter'] != 0:
                day = weekdays[datetime.date(datetime.strptime(
                    self.data['last_message_date'], '%Y-%m-%d')).weekday()]
                self.data[day] = self.data['counter']
            self.data['counter'] = 1
            self.data['last_message_date'] = datetime.date(
                datetime.now()).__str__()
        self.data['orator_total_messages'] += 1

    def decrease_orator_counter(self, amount: int = 1) -> None:
        """Decrementa il contatore dei messaggi del giorno corrente.
        Impedisce che il contatore vada sotto zero, in caso il parametro passato
        sia maggiore del valore del contatore questo viene resettato a 0.

        :param amount: numero di messaggi da rimuovere
        """
        if self.data['counter'] - amount >= 0:
            self.data['counter'] -= amount
        else:
            self.data['counter'] = 0
        self.data['orator_total_messages'] -= 1

    def set_orator(self) -> None:
        """Imposta l'afler come oratore. Consiste in tre operazioni:
        - impostare orator=True
        - salvare la data di scadenza
        - azzerare tutti i contatori dei messaggi
        """
        self.data['orator'] = True
        self.data['orator_expiration'] = datetime.date(
            datetime.now()
            + timedelta(days=Config.get_config().orator_duration)).__str__()
        for i in weekdays:
            self.data[weekdays.get(i)] = 0

    def is_orator_expired(self) -> bool:
        """Controlla se l'assegnazione del ruolo oratore è scaduta.

        :returns: True se orator=True e il ruolo è scaduto, False se orator=True e il ruolo
        non è scaduto oppure se orator=False (l'afler non è oratore)
        :rtype: bool
        """
        if not self.data['orator']:
            return False
        orator_expiration = datetime.date(datetime.strptime(
            self.data['orator_expiration'], '%Y-%m-%d'))
        if orator_expiration <= datetime.date(datetime.now()):
            return True
        else:
            return False

    def remove_orator(self) -> None:
        """Rimuove il ruolo oratore. Consiste in due operazioni:
        - impostare orator=False
        - impostare la data di scadenza a None
        """
        self.data['orator'] = False
        self.data['orator_expiration'] = None

    def set_dank(self) -> None:
        """Imposta l'afler come cazzaro, salvando la data di scadenza
        del ruolo.
        """
        self.data['dank'] = True
        self.data['dank_messages_buffer'] = 0
        self.data['dank_first_message_timestamp'] = None
        expiration = (datetime.now()
                      + timedelta(days=Config.get_config().dank_duration))
        self.data['dank_expiration'] = expiration.isoformat(timespec='hours')

    def increase_dank_counter(self) -> None:
        """
        Aumenta il contatore dei messaggi per il ruolo cazzaro.
        Se la finestra di tempo è scaduta (o se non è mai stato mandato
        un messaggio in precedenza), aggiorna il timestamp e imposta il
        buffer a 1.
        """
        expired = True
        now = datetime.now()
        if self.data['dank_first_message_timestamp'] is not None:
            old_timestamp = datetime.fromisoformat(
                self.data['dank_first_message_timestamp'])
            elapsed_time = now - old_timestamp
            expired = (
                elapsed_time >= timedelta(days=Config.get_config().dank_duration))
        # 'expired' sarà True se il timestamp è vecchio o se non ce n'è uno
        if expired:
            self.data['dank_first_message_timestamp'] = now.isoformat(
                timespec='hours')
            self.data['dank_messages_buffer'] = 1
        else:
            self.data['dank_messages_buffer'] += 1
        self.data['dank_total_messages'] += 1

    def decrease_dank_counter(self, amount: int = 1) -> None:
        """
        Rimuove una certa quantità di messaggi dal contatore cazzaro.

        :param amount: la quantità di messaggi da sottrarre dal contatore
        """
        self.data['dank_messages_buffer'] -= amount
        if self.data['dank_messages_buffer'] < 0:
            self.data['dank_messages_buffer'] = 0
        self.data['dank_total_messages'] -= amount

    def is_eligible_for_dank(self) -> bool:
        """
        Controlla se l'afler abbia scritto abbastanza messaggi per
        ottenere il ruolo cazzaro.

        :return: True se l'afler ha superato la soglia
        :rtype: bool
        """
        return self.data['dank_messages_buffer'] >= Config.get_config().dank_threshold

    def is_dank_expired(self) -> bool:
        """
        Controlla se la scadenza del ruolo cazzaro è stata raggiunta.

        :return: True se la scadenza è stata raggiunta
        :rtype: bool
        """
        if self.data['dank']:
            expiration = datetime.fromisoformat(self.data['dank_expiration'])
            if expiration <= datetime.now():
                return True
        return False

    def remove_dank(self) -> None:
        """Rimuove il ruolo cazzaro. Consiste in due operazioni:
        - impostare dank=False
        - impostare la data di scadenza a None
        """
        self.data['dank'] = False
        self.data['dank_expiration'] = None

    def modify_warn(self, count: int) -> None:
        """Modifica il conteggio dei warn dell'afler. Il parametro count può essere sia
        positivo (incrementare i warn) che negativo (decrementare i warn). La data di ultima violazione è
        aggiustata di conseguenza. Impedisce di avere un totale warn negativo. Se tutti i warn sono
        rimossi anche la data di ultima violazione è azzerata.

        :param count: il numero di warn da aggiungere/rimuovere
        """
        self.data['violations_count'] += count
        if count > 0:
            # modifica la data solo se sono aggiunti
            self.data['last_violation_count'] = datetime.date(
                datetime.now()).__str__()
        if self.data['violations_count'] <= 0:
            self.data['violations_count'] = 0
            self.data['last_violation_count'] = None

    def warn_count(self) -> int:
        """Ritorna il numero di warn che l'afler ha accumulato.

        :returns: il numero di warn accumulati
        :rtype: int
        """
        return self.data['violations_count']

    # METODI A SUPPORTO DELLA LOGICA DI CONTROLLO RUOLI E VIOLAZIONI

    def reset_violations(self) -> int:
        """Azzera le violazioni dell'afler se necessario.

        :returns: il numero di violazioni rimosse
        :rtype: int
        """
        if self.data['last_violation_count'] is not None:
            expiration = datetime.date(datetime.strptime(
                self.data['last_violation_count'], '%Y-%m-%d'))
            if (expiration + timedelta(days=Config.get_config().violations_reset_days)) <= (datetime.date(datetime.now())):
                self.data['violations_count'] = 0
                self.data['last_violation_count'] = None

    def forget_last_week(self) -> None:
        """Rimuove dal conteggio i messaggi risalenti a 7 giorni fa."""
        self.data[weekdays.get(datetime.today().weekday())] = 0

    def clean(self) -> None:
        """Si occupa di controllare il campo last_message_date e sistemare di conseguenza il
        conteggio dei singoli giorni.
        """
        if (self.data['last_message_date'] is None) or (self.data['last_message_date'] == datetime.date(datetime.now()).__str__()):
            # (None) tecnicamente previsto da add_warn se uno viene warnato senza aver mai scritto
            # (Oggi) vuol dire che il bot è stato riavviato a metà giornata non devo toccare i contatori
            return
        elif self.data['last_message_date'] == datetime.date(datetime.today() - timedelta(days=1)).__str__():
            # messaggio di ieri, devo salvare il counter nel giorno corrispondente
            if self.data['counter'] != 0:
                day = weekdays[datetime.date(
                    datetime.today() - timedelta(days=1)).weekday()]
                self.data[day] = self.data['counter']
                self.data['counter'] = 0
        else:
            # devo azzerare tutti i giorni della settimana tra la data segnata (esclusa) e oggi (incluso)
            # in teoria potrei anche eliminare solo il giorno precedente contando sul fatto che venga
            # eseguito tutti i giorni ma preferisco azzerare tutti in caso di downtime di qualche giorno
            if self.data['counter'] != 0:
                day = weekdays[datetime.date(datetime.strptime(
                    self.data['last_message_date'], '%Y-%m-%d')).weekday()]
                self.data[day] = self.data['counter']
                self.data['counter'] = 0
            last_day = datetime.date(datetime.strptime(
                self.data['last_message_date'], '%Y-%m-%d')).weekday()
            today = datetime.today().weekday()
            while last_day != today:
                last_day += 1
                if last_day > 6:
                    last_day = 0
                self.data[weekdays[last_day]] = 0

    def count_orator_messages(self) -> int:
        """Ritorna il conteggio totale dei messaggi dei 7 giorni precedenti, ovvero il campo
        counter + tutti gli altri giorni salvati escluso il giorno corrente.

        :returns: il conteggio dei messaggi
        :rtype: int
        """
        count: int = 0
        for i in weekdays:
            if i != datetime.today().weekday():
                count += self.data[weekdays.get(i)]
        count += self.data['counter']
        return count

    def count_consolidated_messages(self) -> int:
        """Ritorna il conteggio dei messaggi orator salvati nei campi mon, tue,
        wed, ... non include counter.
        Lo scopo è contare i messaggi che sono stati consolidati nello
        storico ai fini di stabilire se si è raggiunta la soglia dell'oratore.

        :returns: il conteggio dei messaggi
        :rtype: int
        """
        count: int = 0
        for i in weekdays:
            count += self.data[weekdays.get(i)]
        return count



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
    _archive_instance: ClassVar[Archive] = None

    def __init__(self) -> None:
        # è sbagliato creare un'istanza, è un singleton
        raise RuntimeError(
            'Non istanziare archivio, usa Archive.get_instance()')

    @classmethod
    def get_instance(cls) -> Archive:
        """Ritorna l'unica istanza dell'archivio."""
        if cls._archive_instance is None:
            cls.load_archive()
        return cls._archive_instance

    @classmethod
    def load_archive(cls):
        """Carica l'archivio da file e lo salva in archive.
        Se non esiste lo crea vuoto. Se chiamato ulteriormente a bot
        avviato, serve a refreshare l'archivio, rileggendo il file.
        """
        try:
            with open('aflers.json', 'r') as file:
                raw_archive: Dict[str, Any] = json.load(file)
                # conversione degli id da str a int così come sono su discord
                archive: Dict[int, Any] = {}
                for k in raw_archive:
                    archive[int(k)] = raw_archive[k]
        except FileNotFoundError:
            with open('aflers.json', 'w+') as file:
                archive: Dict[int, Any] = {}
        finally:
            # Serve creare un'istanza dell'archivio all'avvio.
            # Questo non è il caso invece quando si vuole fare il refresh
            # dell'archivio dopo aver modificato i campi manualmente.
            if cls._archive_instance is None:
                cls._archive_instance = cls.__new__(cls, archive)
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
        return self.archive.keys()

    def values(self) -> List[Afler]:
        """Ritorna una lista con tutti i dati degli aflers salvati nell'archivio.
        Pensato per essere usato come il metodo values() di un dizionario

        :returns: lista con tutti gli afler
        :rtype: List[Afler]
        """
        return self.wrapped_archive.values()

    def save(self, filename: str='aflers.json') -> None:
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
            regex_word = '+ *\W*'.join(word)
            match = re.search(regex_word, text_to_check)
            if match is not None:
                return True
        return False


class BotLogger():
    """Logging degli eventi del server in un canale dedicato. Utilizzato per inviare
    messaggi sul canale di log del server per tenere traccia degli eventi quali warn,
    entrata/uscita membri, messaggi rimossi, etc.

    Attributes
    -------------
    _logger: BotLogger   attributo di classe, contiene l'istanza del logger

    Classmethods
    -------------
    create_instance()   inizializza l'istanza dell logger
    get_instance()   ritorna l'unica istanza del logger

    Methods
    -------------
    initialize()   coroutine, inizializza il canale su cui viene fatto il logging
    log()   coroutine, compila il messaggio e lo invia nel canale
    """
    _logger: ClassVar[BotLogger] = None

    def __init__(self) -> None:
        # attributi sono qua solo per dichiararli
        self.channel: discord.TextChannel
        raise RuntimeError(
            'Usa BotLogger.create_instance per istanziare il logger')

    @classmethod
    def create_instance(cls, bot) -> BotLogger:
        """Crea e ritorna l'istanza del logger e ne inizializza gli attributi.

        :param bot: il bot
        """
        if cls._logger is None:
            cls._logger = cls.__new__(cls)
            cls._logger.channel = None
        return cls._logger

    @classmethod
    def get_instance(cls) -> BotLogger:
        """Ritorna l'unica istanza del logger."""
        return cls._logger

    async def initialize(self, bot: commands.Bot) -> None:
        """Inizializza il logger caricando il canale dedicato. La chiamata
        a questo metodo deve essere fatta una volta sola prima che il logger
        possa procedere con il logging.

        :param bot: il bot
        """
        self.channel = await bot.fetch_channel(Config.get_config().log_channel_id)

    async def log(self,  msg: str, media: List[discord.Attachment]=None) -> None:
        """Compila il messaggio da inviare nel canale. Il formato
        è il seguente:

        YYYY-MM-DD HH:MM:SS.DDDDDD  <msg>

        La data arriva da datetime.now()

        :param msg: il messaggio con l'evento da loggare
        :param media: eventuali allegati del messaggio (immagini, video, etc)
        """
        timestamp = datetime.now()
        msg = f'`{timestamp}`\n{msg}'
        if self.channel is None:
            # fallback sul terminale
            print(msg)
        log_message = discord.Embed(
            title='Log event',
            description=msg,
            # Il timestamp dell'embed è regolato da discord, lo converto in UTC
            timestamp=timestamp.astimezone(timezone.utc)
        )
        files: List[discord.File] = [await m.to_file() for m in media] if media else None
        await self.channel.send(embed=log_message, files=files)


class ConfigFields(TypedDict):
    """Helper per definire la struttura del file di config"""
    guild_id: int
    main_channel_id: int
    presentation_channel_id: int
    welcome_channel_id: int
    log_channel_id: int
    current_prefix: str
    moderation_roles_id: List[int]
    afl_role_id: int
    orator_role_id: int
    orator_category_id: int
    orator_threshold: int
    orator_duration: int
    dank_role_id: int
    dank_category_id: int
    dank_threshold: int
    dank_time_window: int
    dank_duration: int
    exceptional_channels_id: List[int]
    poll_channel_id: int
    under_surveillance_id: int
    violations_reset_days: int
    nick_change_days: int
    bio_length_limit: int
    greetings: str


class Config():
    """Gestione dei parametri di configurazione del bot. Salva tutti i parametri in un dizionario
    che può essere usato dal resto del bot per svolgere la sua funzione. I parametri possono essere
    aggiornati in ogni momento ricaricando i valori dal file config.json che si aspetta di trovare
    nella cartella del bot. Non è fornito un metodo __init__ poichè questa classe è pensata solo per
    utilizzare metodi e attributi statici.

    Attributes
    -------------
        guild_id: id del server in cui contare i messaggi
        main_channel_id: canale dei messaggi di sistema del bot
        presentation_channel_id: canale in cui i nuovi membri si presentano prima dell'ammissione
        welcome_channel_id: canale di benvenuto in cui si annunciano i nuovi membri
        log_channel_id: canale del server in cui si ricevono i messaggi di log del bot
        current_prefix: prefisso per i comandi del bot
        moderation_roles_id: [id dei ruoli di moderazione separati da virgola se più di uno]
        afl_role_id: id del ruolo AFL
        orator_role_id: id del ruolo oratore
        orator_category_id: id della categoria dei canali rilevanti al conteggio oratore
        orator_threshold: numero di messaggi da mandare prima di ricevere il ruolo oratore
        orator_duration: durata del ruolo oratore in GIORNI
        dank_role_id: id del ruolo cazzari
        dank_category_id: id della categoria dei canali rilevanti al conteggio cazzaro
        dank_threshold: numero di messaggi da mandare prima di ricevere il ruolo cazzaro
        dank_time_window: giorni a disposizione per mandare i messaggi per il ruolo cazzaro
        dank_duration: durata del ruolo cazzaro in GIORNI
        exceptional_channels_id: [elenco dei canali non controllati dal bot, separati da virgola se più di uno]
        poll_channel_id: canale in cui controllare le reaction alle proposte
        under_surveillance_id: id del ruolo sotto sorveglianza (vedi regole)
        violations_reset_days: tempo dopo cui si resettano le violazioni in giorni
        nick_change_days: giorni concessi tra un cambio di nickname e l'altro (0 nessun limite)
        bio_length_limit: massimo numero di caratteri per la bio
        greetings: messaggio di benvenuto per i nuovi membri

    Methods
    -------------
    load()  carica i valori dal file config.json
    """
    _instance: ClassVar[Config] = None

    def __init__(self) -> None:
        raise RuntimeError('use Config.get_config() instead')

    def __str__(self) -> str:
        """Rappresentazione della configurazione del bot come stringa.

        :returns: la configurazione corrente del bot
        :rtype: str
        """
        attributes = vars(self)
        string = ''
        for key in attributes:
            string += f'{key} = {attributes[key]}\n'
        return string

    @classmethod
    def get_config(cls):
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            cls._instance.load()
        return cls._instance

    def load(self) -> bool:
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
                self._load_config(data)
                print('configurazione ricaricata correttamente')
                return True
        except (FileNotFoundError, json.decoder.JSONDecodeError) as e:
            print(e)
            print(
                'errore nella ricarica della configurazione, mantengo configurazione precedente')
            return False

    def _load_config(self, data: ConfigFields) -> None:
        """Converte i valori letti dal dizionario nei tipi corretti. Chiamato dalla load, non
        utilizzare direttamente questo metodo.
        """
        self.guild_id = int(data['guild_id'])
        self.main_channel_id = int(data['main_channel_id'])
        self.presentation_channel_id = int(data['presentation_channel_id'])
        self.welcome_channel_id = int(data['welcome_channel_id'])
        self.log_channel_id = int(data['log_channel_id'])
        self.current_prefix = data['current_prefix']
        self.moderation_roles_id = []
        for mod in data['moderation_roles_id']:
            self.moderation_roles_id.append(int(mod))
        self.afl_role_id = int(data['afl_role_id'])
        self.orator_role_id = int(data['orator_role_id'])
        self.orator_category_id = int(data['orator_category_id'])
        self.orator_threshold = data['orator_threshold']
        self.orator_duration = data['orator_duration']
        self.dank_role_id = int(data['dank_role_id'])
        self.dank_category_id = int(data['dank_category_id'])
        self.dank_threshold = data['dank_threshold']
        self.dank_time_window = data['dank_time_window']
        self.dank_duration = data['dank_duration']
        self.exceptional_channels_id = []
        for channel in data['exceptional_channels_id']:
            self.exceptional_channels_id.append(int(channel))
        self.poll_channel_id = int(data['poll_channel_id'])
        self.under_surveillance_id = int(data['under_surveillance_id'])
        self.violations_reset_days = data['violations_reset_days']
        self.nick_change_days = data['nick_change_days']
        self.bio_length_limit = data['bio_length_limit']
        self.greetings = data['greetings']

    def save(self) -> None:
        """Save the current config"""
        update_json_file(vars(self), 'config.json')


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
                'https:\/\/www\.amazon\..*\/.*\/[A-Z0-9]{10}', word)[0]
    return cleaned_link
