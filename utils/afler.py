from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from utils.config import Config

import discord

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
    last_violation_date: Optional[date]     data di ultima violazione

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
            'last_violation_date': None,
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
    def escaped_nick(self) -> str:
        """Restituisce il nickname dell'afler facendo escape di eventuale markdown
        presente. Se non contiene markdown è equivalente al nick. Utile per stampare
        il nickname in un messaggio evitando di formattare il markdown presente.

        :returns: il nickname con le sequenze di markdown escapate
        :rtype: str
        """
        return discord.utils.escape_markdown(self.data['nick'])

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
        Aggiorna la data dell'ultimo cambiamento del nick ad oggi.

        :param new_nick: nuovo nickname
        """
        self.data['nick'] = new_nick
        self.data['last_nick_change'] = date.today().isoformat()

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
        :rtype: Optional[date]
        """
        if self.data['orator_expiration'] is not None:
            return date.fromisoformat(self.data['orator_expiration'])
        else:
            return None

    @property
    def dank_expiration(self) -> Optional[datetime]:
        """Ritorna la data di scadenza del ruolo cazzaro.

        :returns: data di scadenza cazzaro
        :rtype: Optional[datetime]
        """
        if self.data['dank_expiration'] is not None:
            return datetime.fromisoformat(self.data['dank_expiration'])
        else:
            return None

    @property
    def last_nick_change(self) -> date:
        """Ritorna la data dell'utlimo cambio di nickname

        :returns: data ultimo cambio
        :rtype: date
        """
        return date.fromisoformat(self.data['last_nick_change'])

    @property
    def last_message_date(self) -> Optional[date]:
        """Ritorna la data dell'ultimo messaggio valido per il conteggio dell'oratore.

        :returns: data ultimo messaggio
        :rtype: Optional[date]
        """
        if self.data['last_message_date'] is not None:
            return date.fromisoformat(self.data['last_message_date'])
        else:
            return None

    @property
    def last_violation_date(self) -> Optional[date]:
        """Ritorna la data dell'ultima violazione.

        :returns: data ultima violazione
        :rtype: Optional[date]
        """
        if self.data['last_violation_date'] is not None:
            return date.fromisoformat(self.data['last_violation_date'])
        else:
            return None

    def increase_orator_counter(self) -> None:
        """Aggiorna il contatore oratore dell'utente autore del messaggio passato. In caso l'utente non sia
        presente nel file aflers.json lo aggiunge inizializzando tutti i contatori dei giorni a 0 e counter a 1.
        Si occupa anche di aggiornare il campo 'last_message_date'.
        """
        today = date.today()
        if self.data['last_message_date'] == today:
            # messaggi dello stesso giorno, continuo a contare
            self.data['counter'] += 1
        elif self.data['last_message_date'] is None:
            # primo messaggio della persona
            self.data['counter'] = 1
            self.data['last_message_date'] = today
        else:
            # è finito il giorno, salva i messaggi di 'counter' nel
            # giorno corrispondente e aggiorna data ultimo messaggio
            if self.data['counter'] != 0:
                day = weekdays[date.fromisoformat(
                    self.data['last_message_date']).weekday()]
                self.data[day] = self.data['counter']
            self.data['counter'] = 1
            self.data['last_message_date'] = today.isoformat()
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
            + timedelta(days=Config.get_config().orator_duration)).isoformat()
        for i in weekdays:
            self.data[weekdays[i]] = 0

    def is_orator_expired(self) -> bool:
        """Controlla se l'assegnazione del ruolo oratore è scaduta.

        :returns: True se orator=True e il ruolo è scaduto, False se orator=True e il ruolo
        non è scaduto oppure se orator=False (l'afler non è oratore)
        :rtype: bool
        """
        if not self.data['orator']:
            return False
        orator_expiration = date.fromisoformat(
            self.data['orator_expiration'])
        if orator_expiration <= date.today():
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
            self.data['last_violation_date'] = date.today().isoformat()
        if self.data['violations_count'] <= 0:
            self.data['violations_count'] = 0
            self.data['last_violation_date'] = None

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
        violations_count = 0
        if self.data['last_violation_date'] is not None:
            expiration = date.fromisoformat(
                self.data['last_violation_date'])
            if (expiration + timedelta(days=Config.get_config().violations_reset_days)) <= date.today():
                violations_count = self.data['violations_count']
                self.data['violations_count'] = 0
                self.data['last_violation_date'] = None
        return violations_count

    def forget_last_week(self) -> None:
        """Rimuove dal conteggio i messaggi risalenti a 7 giorni fa."""
        self.data[weekdays[date.today().weekday()]] = 0

    def clean(self) -> None:
        """Si occupa di controllare il campo last_message_date e sistemare di conseguenza il
        conteggio dei singoli giorni.
        """
        if (self.data['last_message_date'] is None) or (self.data['last_message_date'] == date.today().isoformat()):
            # (None) tecnicamente previsto da add_warn se uno viene warnato senza aver mai scritto
            # (Oggi) vuol dire che il bot è stato riavviato a metà giornata non devo toccare i contatori
            return
        elif self.data['last_message_date'] == datetime.date(datetime.today() - timedelta(days=1)).isoformat():
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
                day = weekdays[date.fromisoformat(
                    self.data['last_message_date']).weekday()]
                self.data[day] = self.data['counter']
                self.data['counter'] = 0
            last_day = date.fromisoformat(
                self.data['last_message_date']).weekday()
            today = date.today().weekday()
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
            if i != date.today().weekday():
                count += self.data[weekdays[i]]
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
            count += self.data[weekdays[i]]
        return count
