from __future__ import annotations
"""Funzionalità condivise tra le diverse cog per facilitare la manutenzione. In particolare:
Classi:
- Afler per eseguire operazioni sugli elementi dell' archivio
- Archive archivio con i dati
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
from typing import List, Optional

# utile per passare dal giorno della settimana restituito da weekday() direttamente
# al campo corrispondente nel dizionario del json
weekdays = {
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
    data: Dict[] contiene i dati dell'afler
    nick: str    contiene il nickname dell'afler
    bio: str     contiene la bio dell'afler
    active: bool flag per dire se è attivo o meno

    Classmethods
    -------------
    new_entry(nick) crea un nuovo afler
    from_archive(data) crea un afler con i dati letti dall'archivio

    Methods
    -------------
    last_nick_change() ritorna la data dell'ultimo cambio nickname
    last_message_date() ritorna la data dell'ultimo messaggio valido per l'attivo
    last_violations_count() ritorna la data di ultima violazione
    increase_counter() incrementa il contatore messaggi
    decrease_counter() decrementa il contatore dei messaggi del giorno corrente
    set_active() imposta l'afler come attivo
    is_active_expired() controlla se il ruolo attivo è scaduto
    set_inactive() rimuove l'attivo
    modify_warn() aggiunge o rimuove warn all'afler
    warn_count() ritorna il numero di warn
    reset_violations() azzera il numero di violazioni commesse
    forget_last_week() azzera il contatore corrispondente a 7 giorni fa
    clean() sistema i dati salvati al cambio di giorno
    count_messages() conta i messaggi totali
    count_consolidated_messages() conta solo i messaggi dei giorni precedenti a oggi
    """
    def __init__(self, data: dict) -> None:
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
            'last_nick_change': datetime.date(datetime.now()).__str__(),
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
            'active': False,
            'expiration': None,
            'bio': None
        })

    @classmethod
    def from_archive(cls, afler_data: dict) -> Afler:
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
    def bio(self) -> None:
        """Restituisce la bio dell'afler
        
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
    def active(self) -> bool:
        """Ritorna lo stato attivo dell'afler.
        
        :returns: True se attivo, False altrimenti
        :rtype: bool
        """
        return self.data['active']

    def active_expiration(self) -> Optional[datetime.date]:
        """Ritorna la data di scadenza del ruolo attivo.
        
        :returns: data di scadenza attivo
        :rtype: Optional[datetime.date]
        """
        if self.data['expiration'] is not None:
            return datetime.date(datetime.strptime(self.data['expiration'], '%Y-%m-%d'))
        else:
            return None

    def last_nick_change(self) -> datetime.date:
        """Ritorna la data dell'utlimo cambio di nickname
        
        :returns: data ultimo cambio
        :rtype: datetime.date
        """
        return datetime.date(datetime.strptime(self.data['last_nick_change'], '%Y-%m-%d'))

    def last_message_date(self) -> Optional[datetime.time]:
        """Ritorna la data dell'ultimo messaggio valido per il conteggio dell'attivo.
        
        :returns: data ultimo messaggio
        :rtype: Optional[datetime.date]
        """
        if self.data['last_message_date'] is not None:
            return datetime.date(datetime.strptime(self.data['last_message_date'], '%Y-%m-%d'))
        else:
            return None

    def last_violations_count(self) -> Optional[datetime.date]:
        """Ritorna la data dell'ultima violazione.
        
        :returns: data ultima violazione
        :rtype: Optional[datetime.date]
        """
        if self.data['last_violation_count'] is not None:
            return datetime.date(datetime.strptime(self.data['last_violation_count'], '%Y-%m-%d'))
        else:
            return None

    def increase_counter(self) -> None:
        """Aggiorna il contatore dell'utente autore del messaggio passato. In caso l'utente non sia presente
        nel file aflers.json lo aggiunge inizializzando tutti i contatori dei giorni a 0 e counter a 1.
        Si occupa anche di aggiornare il campo 'last_message_date'.
        """
        if self.data['last_message_date'] == datetime.date(datetime.now()).__str__():
            # messaggi dello stesso giorno, continuo a contare
            self.data['counter'] += 1
        elif self.data['last_message_date'] is None:
            # primo messaggio della persona
            self.data['counter'] = 1
            self.data['last_message_date'] = datetime.date(datetime.now()).__str__()
        else:
            # è finito il giorno, salva i messaggi di 'counter' nel giorno corrispondente e aggiorna data ultimo messaggio
            if self.data['counter'] != 0:
                day = weekdays[datetime.date(datetime.strptime(self.data['last_message_date'], '%Y-%m-%d')).weekday()]
                self.data[day] = self.data['counter']
            self.data['counter'] = 1
            self.data['last_message_date'] = datetime.date(datetime.now()).__str__()

    def decrease_counter(self, amount: int=1) -> None:
        """Decrementa il contatore dei messaggi del giorno corrente.
        Impedisce che il contatore vada sotto zero, in caso il parametro passato
        sia maggiore del valore del contatore questo viene resettato a 0.
        
        :param amount: numero di messaggi da rimuovere
        """
        if self.data['counter'] - amount >= 0:
            self.data['counter'] -= amount
        else:
            self.data['counter'] = 0

    def set_active(self) -> None:
        """Imposta l'afler come attivo. Consiste in tre operazioni:
        - impostare active=True
        - salvare la data di scadenza
        - azzerare tutti i contatori dei messaggi
        """
        self.data['active'] = True
        self.data['expiration'] = datetime.date(datetime.now() + timedelta(days=Config.config['active_duration'])).__str__()
        for i in weekdays:
            self.data[weekdays.get(i)] = 0

    def is_active_expired(self) -> bool:
        """Controlla se l'assegnazione del ruolo attivo è scaduta.
        
        :returns: True se active=True e il ruolo è scaduto, False se active=True e il ruolo
        non è scaduto oppure se active=False (l'afler non è attivo) 
        :rtype: bool
        """
        if not self.data['active']:
            return False
        expiration = datetime.date(datetime.strptime(self.data['expiration'], '%Y-%m-%d'))
        if expiration <= ((datetime.date(datetime.now()))):
            return True
        else: 
            return False

    def set_inactive(self) -> None:
        """Imposta l'afler come non attivo. Consiste in due operazioni:
        - impostare active=False
        - impostare la data di scadenza a None
        """
        self.data['active'] = False
        self.data['expiration'] = None

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
            self.data['last_violation_count'] = datetime.date(datetime.now()).__str__()
        if self.data['violations_count'] <= 0:
            self.data['violations_count'] = 0
            self.data['last_violation_count'] = None

    def warn_count(self) -> int:
        """Ritorna il numero di warn che l'afler ha accumulato.
        
        :returns: il numero di warn accumulati
        :rtype: int
        """
        return self.data['violations_count']

    ## METODI A SUPPORTO DELLA LOGICA DI CONTROLLO ATTIVO E VIOLAZIONI

    def reset_violations(self) -> None:
        """Azzera le violazioni dell'afler se necessario."""
        if self.data['last_violation_count'] is not None:
            expiration = datetime.date(datetime.strptime(self.data['last_violation_count'], '%Y-%m-%d'))
            if (expiration + timedelta(days=Config.config["violations_reset_days"])) <= (datetime.date(datetime.now())):
                print('reset violazioni di ' + self.data['nick'])
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
                day = weekdays[datetime.date(datetime.today() - timedelta(days=1)).weekday()]
                self.data[day] = self.data['counter']
                self.data['counter'] = 0
        else:
            # devo azzerare tutti i giorni della settimana tra la data segnata (esclusa) e oggi (incluso)
            # in teoria potrei anche eliminare solo il giorno precedente contando sul fatto che venga
            # eseguito tutti i giorni ma preferisco azzerare tutti in caso di downtime di qualche giorno
            if self.data['counter'] != 0:
                day = weekdays[datetime.date(datetime.strptime(self.data['last_message_date'], '%Y-%m-%d')).weekday()]
                self.data[day] = self.data['counter']
                self.data['counter'] = 0
            last_day = datetime.date(datetime.strptime(self.data['last_message_date'], '%Y-%m-%d')).weekday()
            today = datetime.today().weekday()
            while last_day != today:
                last_day += 1
                if last_day > 6:
                    last_day = 0
                self.data[weekdays[last_day]] = 0

    def count_messages(self) -> int:
        """Ritorna il conteggio totale dei messaggi dei 7 giorni precedenti, ovvero il campo
        counter + tutti gli altri giorni salvati escluso il giorno corrente.

        :returns: il conteggio dei messaggi
        :rtype: int
        """
        count = 0
        for i in weekdays:
            if i != datetime.today().weekday():
                count += self.data[weekdays.get(i)]
        count += self.data['counter']
        return count

    def count_consolidated_messages(self) -> int:
        """Ritorna il conteggio dei messaggi salvati nei campi mon, tue, wed, ... non include counter
        Lo scopo è contare i messaggi che sono stati consolidati nello storico ai fini di stabilire se
        si è raggiunta la soglia dell'attivo.

        :returns: il conteggio dei messaggi
        :rtype: int
        """
        count = 0
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
    get()          ritorna i dati dell'afler richiesto
    add()          aggiunge una nuova entry all'archivio
    remove()       rimuove l'afler dall'archivio
    is_present()   controlla se l'afler è presente o meno
    keys()         ritorna gli id di tutti gli aflers salvati
    values()       ritorna tutte le istanze di afler salvate
    save()         salva le modifiche fatte all'archivio
    """
    _archive_instance = None

    def __init__(self, archive: dict) -> None:
        # è sbagliato creare un'istanza, è un singleton
        raise RuntimeError('Non istanziare archivio, usa Archive.get_instance()')

    @classmethod
    def get_instance(cls) -> Archive:
        """Ritorna l'unica istanza dell'archivio."""
        if cls._archive_instance is None:
            cls.load_archive()
        return cls._archive_instance

    @classmethod
    def load_archive(cls):
        """Carica l'archivio da file e lo salva in archive. Se non esiste lo crea vuoto."""
        try:
            with open('aflers.json', 'r') as file:
                raw_archive = json.load(file)
                # conversione degli id da str a int così come sono su discord
                archive = {}
                for k in raw_archive:
                    archive[int(k)] = raw_archive[k]
        except FileNotFoundError:
            with open('aflers.json','w+') as file:
                archive = {}
        finally:
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
                cls._archive_instance.wrapped_archive[key] = Afler.from_archive(archive[key])
    
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
    
    def save(self):
        """Salva su disco le modifiche effettuate all'archivio.
        
        NOTA: per ora non viene mai chiamato automaticamente dagli altri metodi
        ma deve essere esplicitamente usato quando si vogliono salvare le modifiche.
        L'idea è lasciare più flessibilità, consentendo di effettuare operazioni diverse
        e poi salvare tutto alla fine.
        """
        update_json_file(self.archive, 'aflers.json')

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
    _logger = None

    def __init__(self) -> None:
        raise RuntimeError

    @classmethod
    def create_instance(cls, bot) -> BotLogger:
        """Crea e ritorna l'istanza del logger e ne inizializza gli attributi.
        
        :param bot: il bot
        """
        if cls._logger is None:
            cls._logger = cls.__new__(cls)
            cls._logger.bot = bot
            cls._logger.channel = None
        return cls._logger

    @classmethod
    def get_instance(cls) -> BotLogger:
        """Ritorna l'unica istanza del logger."""
        return cls._logger

    async def initialize(self, bot) -> None:
        """Inizializza il logger caricando il canale dedicato. La chiamata
        a questo metodo deve essere fatta una volta sola prima che il logger
        possa procedere con il logging.
        
        :param bot: il bot
        """
        self.channel = await bot.fetch_channel(Config.config['log_channel_id'])
        
    async def log(self,  msg: str) -> None:
        """Compila il messaggio da inviare nel canale. Il formato
        è il seguente:
        
        YYYY-MM-DD HH:MM:SS.DDDDDD  <msg>

        La data arriva da datetime.now()

        :param msg: il messaggio con l'evento da loggare
        """
        timestamp = str(datetime.now())
        msg = '`' + timestamp + '`  ' + msg
        if self.channel is None:
            # fallback sul terminale
            print(msg)
        await self.channel.send(msg)
        
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
        Config.config['log_channel_id'] = int(data['log_channel_id'])
        Config.config['current_prefix'] = data['current_prefix']
        Config.config['moderation_roles_id'] = []
        for mod in data['moderation_roles_id']:
            Config.config['moderation_roles_id'].append(int(mod))
        Config.config['afl_role_id'] = int(data['afl_role_id'])
        Config.config['active_role_id'] = int(data['active_role_id'])
        Config.config['active_channels_id'] = []
        for channel in data['active_channels_id']:
            Config.config['active_channels_id'].append(int(channel))
        Config.config['active_threshold'] = data['active_threshold']
        Config.config['active_duration'] = data['active_duration']
        Config.config['exceptional_channels_id'] = []
        for channel in data['exceptional_channels_id']:
            Config.config['exceptional_channels_id'].append(int(channel))
        Config.config['poll_channel_id'] = int(data['poll_channel_id'])
        Config.config['under_surveillance_id'] = int(data['under_surveillance_id'])
        Config.config['violations_reset_days'] = data['violations_reset_days']
        Config.config['nick_change_days'] = data['nick_change_days']
        Config.config['bio_length_limit'] = data['bio_length_limit']
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
    if len(words) == 1:   # il messaggio non ha spazi, potrebbe essere un link
        word = words[0]
        if word.__contains__('www.amazon'):
            # si assume che i link ai prodotti amazon abbiano tutti la stessa struttura:
            #     https://amazon.identificativo_nazione_o_com/nome_lungo_descrittivo/dp/10CARATTER
            # la regex effettua l'estrazione di questa porzione di link
            cleaned_link = re.findall('https:\/\/www\.amazon\..*\/.*\/[A-Z0-9]{10}', word)[0]
    return cleaned_link
