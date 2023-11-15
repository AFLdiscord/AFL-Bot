from __future__ import annotations
"""Wrapper per eseguire operazioni sugli elementi dell' archivio, ossia
gli aflers
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from utils.config import Config
from utils.shared_functions import next_datetime

import discord


class Afler():
    """Rappresentazione di un membro del server.
    Semplifica le operazioni di lettura/scrittura quando si accede all'archivio.
    È importante implementare questa classe tenendo separata la logica di gestione del bot
    dalla logica di gestione dei dati degli afler.
    Esempio: non controllare la soglia dei messaggi qua ma passare il totale all'esterno dove viene
    fatto il controllo in base alla config del bot

    Attributes
    -------------
    nickname: `str`                         contiene il nickname dell'afler
    bio: `str`                              contiene la bio dell'afler
    orator: `bool`                          flag per dire se è oratore o meno
    dank: `bool`                            flag per dire se è cazzaro o meno
    dank_messages_buffer: `int`             messaggi del ruolo cazzaro inviati nella finestra di tempo
    orator_total_messages: `int`            totale messaggi orator
    dank_total_messages: `int`              totale messaggi dank
    total_messages: `int`                   messaggi totali inviati dall'afler
    orator_expiration: `Optional[date]`     data di scadenza del ruolo oratore
    dank_expiration: `Optional[date]`       data di scadenza del ruolo cazzaro
    last_nick_change: `date`                data dell'ultimo cambio nickname
    last_message_date: `Optional[date]`     data dell'ultimo messaggio valido per l'oratore
    last_violation_date: `Optional[date]`   data di ultima violazione

    Classmethods
    -------------
    new_entry(nick):    crea un nuovo afler
    from_archive(data): crea un afler con i dati letti dall'archivio

    Methods
    -------------
    increase_orator_counter():      incrementa il contatore oratore
    decrease_orator_counter():      decrementa il contatore oratore del giorno corrente
    set_orator():                   imposta l'afler come oratore
    is_orator_expired():            controlla se il ruolo oratore è scaduto
    remove_orator():                rimuove il ruolo oratore
    set_dank():                     imposta l'afler come cazzaro
    increase_dank_counter():        incrementa il contatore cazzaro
    decrease_dank_counter():        decrementa il contatore cazzaro
    is_eligible_for_dank():         controlla se l'afler può ottenere il ruolo cazzaro
    is_dank_expired():              controlla se il ruolo cazzaro è scaduto
    remove_dank():                  rimuove il ruolo cazzaro
    modify_warn():                  aggiunge o rimuove warn all'afler
    warn_count():                   ritorna il numero di warn
    reset_violations():             azzera il numero di violazioni commesse
    forget_last_week():             azzera il contatore corrispondente a 7 giorni fa
    clean():                        sistema i dati salvati al cambio di giorno
    count_orator_messages():        conta i messaggi totali
    count_consolidated_messages():  conta solo i messaggi dei giorni precedenti a oggi
    """

    def __init__(self, data: Dict[str, Any]) -> None:
        """
        :param data: dizionario che contiene i dati dell'afler
        """
        self.nickname: str = data['nickname']
        self.last_nick_change: date = date.fromisoformat(
            data['last_nick_change'])
        self.violations_count: int = data['violations_count']
        _last_violation_date = data['last_violation_date']
        if _last_violation_date is not None:
            _last_violation_date = date.fromisoformat(_last_violation_date)
        self.last_violation_date: Optional[date] = _last_violation_date
        self.bio: Optional[str] = data['bio']
        self.orator: bool = data['orator']
        _orator_expiration = data['orator_expiration']
        if _orator_expiration is not None:
            _orator_expiration = date.fromisoformat(_orator_expiration)
        self.orator_expiration: Optional[date] = _orator_expiration
        self.orator_weekly_buffer: list[int] = list(
            data['orator_weekly_buffer'])
        self.orator_daily_buffer: int = data['orator_daily_buffer']
        _orator_last_message_timestamp = data['orator_last_message_timestamp']
        if _orator_last_message_timestamp is not None:
            _orator_last_message_timestamp = date.fromisoformat(
                _orator_last_message_timestamp)
        self.orator_last_message_timestamp: Optional[date] = _orator_last_message_timestamp
        self.orator_total_messages: int = data['orator_total_messages']
        self.dank: bool = data['dank']
        _dank_expiration = data['dank_expiration']
        if _dank_expiration is not None:
            _dank_expiration = datetime.fromisoformat(
                _dank_expiration).astimezone()
        self.dank_expiration: Optional[datetime] = _dank_expiration
        self.dank_messages_buffer: int = data['dank_messages_buffer']
        _dank_first_message_timestamp = data['dank_first_message_timestamp']
        if _dank_first_message_timestamp is not None:
            _dank_first_message_timestamp = datetime.fromisoformat(
                _dank_first_message_timestamp).astimezone()
        self.dank_first_message_timestamp: Optional[datetime] = _dank_first_message_timestamp
        self.dank_total_messages: int = data['dank_total_messages']

    @classmethod
    def new_entry(cls, nickname: str) -> Afler:
        """Crea un nuovo afler.

        :param nickname: il nickname del nuovo afler

        :returns: l'afler appena creato
        :rtype: Afler
        """
        return cls({
            'nickname': nickname,
            'last_nick_change': date.today().isoformat(),
            'violations_count': 0,
            'last_violation_date': None,
            'bio': None,
            'orator': False,
            'orator_expiration': None,
            'orator_weekly_buffer': [0] * 7,
            'orator_daily_buffer': 0,
            'orator_last_message_timestamp': None,
            'orator_total_messages': 0,
            'dank': False,
            'dank_expiration': None,
            'dank_messages_buffer': 0,
            'dank_first_message_timestamp': None,
            'dank_total_messages': 0,
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
        return discord.utils.escape_markdown(self.nickname)

    @property
    def nick(self) -> str:
        """Restituisce il nickname dell'afler.

        :returns: il nickname dell'afler
        :rtype: str
        """
        return self.nickname

    @nick.setter
    def nick(self, new_nick: str) -> None:
        """Modifica il nome dell'afler.
        Aggiorna la data dell'ultimo cambiamento del nick ad oggi.

        :param new_nick: nuovo nickname
        """
        self.nickname = new_nick
        self.last_nick_change = date.today()

    @property
    def total_messages(self) -> int:
        """Restituisce il numero totale di messaggi inviati dall'afler.
        I totali sono calcolati dalla versione 2.0 del bot.

        :return: il numero totale di messaggi mandati
        :rtype: int
        """
        return self.orator_total_messages + self.dank_total_messages

    def increase_orator_buffer(self) -> None:
        """Aggiorna il buffer oratore."""
        today = date.today()
        if self.orator_last_message_timestamp == today:
            # messaggi dello stesso giorno, continuo a contare
            self.orator_daily_buffer += 1
        elif self.orator_last_message_timestamp is None:
            # primo messaggio della persona
            self.orator_daily_buffer = 1
            self.orator_last_message_timestamp = today
        else:
            # è finito il giorno, salva i messaggi di 'orator_daily_buffer' nel
            # giorno corrispondente e aggiorna data ultimo messaggio
            if self.orator_daily_buffer != 0:
                day = self.orator_last_message_timestamp.weekday()
                self.orator_weekly_buffer[day] = self.orator_daily_buffer
            self.orator_daily_buffer = 1
            self.orator_last_message_timestamp = today
        self.orator_total_messages += 1

    def decrease_orator_buffer(self, amount: int = 1) -> None:
        """Decrementa il buffer oratore

        :param amount: numero di messaggi da rimuovere
        """
        self.orator_daily_buffer = max(0, self.orator_daily_buffer - amount)
        self.orator_total_messages = max(
            0, self.orator_total_messages - amount)

    def set_orator(self) -> None:
        """Imposta l'afler come oratore. Consiste in tre operazioni:
        - impostare orator=True
        - salvare la data di scadenza
        - azzerare tutti i contatori dei messaggi
        """
        self.orator = True
        days = Config.get_config().orator_duration
        self.orator_expiration = date.today() + timedelta(days=days)
        self.orator_weekly_buffer = [0] * 7

    def is_orator_expired(self) -> bool:
        """Controlla se l'assegnazione del ruolo oratore è scaduta.

        :returns: True se orator=True e il ruolo è scaduto, False se orator=True e il ruolo
        non è scaduto oppure se orator=False (l'afler non è oratore)
        :rtype: bool
        """
        if not self.orator:
            return False
        assert (self.orator_expiration is not None)
        if self.orator_expiration <= date.today():
            return True
        else:
            return False

    def remove_orator(self) -> None:
        """Rimuove il ruolo oratore. Consiste in due operazioni:
        - impostare orator=False
        - impostare la data di scadenza a None
        """
        self.orator = False
        self.orator_expiration = None

    def set_dank(self) -> None:
        """Imposta l'afler come cazzaro, salvando la data di scadenza
        del ruolo.
        """
        self.dank = True
        self.dank_messages_buffer = 0
        self.dank_first_message_timestamp = None
        expiration = next_datetime(
            datetime.now(), Config.get_config().dank_duration)
        self.dank_expiration = expiration.replace(
            minute=0, second=0, microsecond=0)

    def increase_dank_counter(self) -> None:
        """Aumenta il contatore dei messaggi per il ruolo cazzaro.
        Se la finestra di tempo è scaduta (o se non è mai stato mandato
        un messaggio in precedenza), aggiorna il timestamp e imposta il
        buffer a 1.
        """
        expired = True
        now = datetime.now().astimezone().replace(
            minute=0, second=0, microsecond=0)
        if self.dank_first_message_timestamp is not None:
            old_timestamp = self.dank_first_message_timestamp
            expired = next_datetime(
                old_timestamp, Config.get_config().dank_duration) <= now
        # 'expired' sarà True se il timestamp è vecchio o se non ce n'è uno
        if expired:
            self.dank_first_message_timestamp = now
            self.dank_messages_buffer = 1
        else:
            self.dank_messages_buffer += 1
        self.dank_total_messages += 1

    def decrease_dank_counter(self, amount: int = 1) -> None:
        """Rimuove una certa quantità di messaggi dal contatore cazzaro.

        :param amount: la quantità di messaggi da sottrarre dal contatore
        """
        self.dank_messages_buffer = max(0, self.dank_messages_buffer - amount)
        self.dank_total_messages = max(0, self.dank_total_messages - amount)

    def is_eligible_for_dank(self) -> bool:
        """Controlla se l'afler abbia scritto abbastanza messaggi per
        ottenere il ruolo cazzaro.

        :return: True se l'afler ha superato la soglia
        :rtype: bool
        """
        return self.dank_messages_buffer >= Config.get_config().dank_threshold

    def is_dank_expired(self) -> bool:
        """Controlla se la scadenza del ruolo cazzaro è stata raggiunta.

        :return: True se la scadenza è stata raggiunta
        :rtype: bool
        """
        if self.dank:
            assert (self.dank_expiration is not None)
            if self.dank_expiration <= datetime.now().astimezone():
                return True
        return False

    def remove_dank(self) -> None:
        """Rimuove il ruolo cazzaro. Consiste in due operazioni:
        - impostare dank=False
        - impostare la data di scadenza a None
        """
        self.dank = False
        self.dank_expiration = None

    def modify_warn(self, count: int) -> None:
        """Modifica il conteggio dei warn dell'afler. Il parametro count può essere sia
        positivo (incrementare i warn) che negativo (decrementare i warn). La data di ultima violazione è
        aggiustata di conseguenza. Impedisce di avere un totale warn negativo. Se tutti i warn sono
        rimossi anche la data di ultima violazione è azzerata.

        :param count: il numero di warn da aggiungere/rimuovere
        """
        self.violations_count = max(0, self.violations_count + count)
        if count > 0:
            # modifica la data solo se sono aggiunti
            self.last_violation_date = date.today()
        else:
            self.last_violation_date = None

    def warn_count(self) -> int:
        """Ritorna il numero di warn che l'afler ha accumulato.

        :returns: il numero di warn accumulati
        :rtype: int
        """
        return self.violations_count

    # METODI A SUPPORTO DELLA LOGICA DI CONTROLLO RUOLI E VIOLAZIONI

    def reset_violations(self) -> int:
        """Azzera le violazioni dell'afler se necessario.

        :returns: il numero di violazioni rimosse
        :rtype: int
        """
        violations_count = 0
        if self.last_violation_date is not None:
            if (self.last_violation_date + timedelta(days=Config.get_config().violations_reset_days)) <= date.today():
                violations_count = self.violations_count
                self.violations_count = 0
                self.last_violation_date = None
        return violations_count

    def forget_last_week(self) -> None:
        """Rimuove dal conteggio i messaggi risalenti a 7 giorni fa."""
        self.orator_weekly_buffer[date.today().weekday()] = 0

    def clean_orator_buffer(self) -> None:
        """Si occupa di controllare il campo orator_last_message_timestamp
        e sistemare di conseguenza il conteggio dei singoli giorni.
        """
        today = date.today()
        if (self.orator_last_message_timestamp is None) or (self.orator_last_message_timestamp == today):
            # (None) tecnicamente previsto da add_warn se uno viene warnato senza aver mai scritto
            # (Oggi) vuol dire che il bot è stato riavviato a metà giornata non devo toccare i contatori
            return
        elif self.orator_last_message_timestamp == today - timedelta(days=1):
            # messaggio di ieri, devo salvare il counter nel giorno corrispondente
            day = (today.weekday() - 1) % 7
        else:
            # devo azzerare tutti i giorni della settimana tra la data segnata (esclusa) e oggi (incluso)
            # in teoria potrei anche eliminare solo il giorno precedente contando sul fatto che venga
            # eseguito tutti i giorni ma preferisco azzerare tutti in caso di downtime di qualche giorno
            day = d = self.orator_last_message_timestamp.weekday()
            while d != today.weekday():
                d = (d + 1) % 7
                self.orator_weekly_buffer[d] = 0
        if self.orator_daily_buffer != 0:
            self.orator_weekly_buffer[day] = self.orator_daily_buffer
            self.orator_daily_buffer = 0

    def count_orator_messages(self) -> int:
        """Ritorna il conteggio totale dei messaggi dei 7 giorni precedenti, ovvero il campo
        counter + tutti gli altri giorni salvati escluso il giorno corrente.

        :returns: il conteggio dei messaggi
        :rtype: int
        """
        return (
            sum(self.orator_weekly_buffer)
            - self.orator_weekly_buffer[date.today().weekday()]
            + self.orator_daily_buffer
        )

    def count_consolidated_messages(self) -> int:
        """Ritorna il conteggio dei messaggi orator.
        Lo scopo è contare i messaggi che sono stati consolidati nello
        storico ai fini di stabilire se si è raggiunta la soglia dell'oratore.

        :returns: il conteggio dei messaggi
        :rtype: int
        """
        return sum(self.orator_weekly_buffer)
