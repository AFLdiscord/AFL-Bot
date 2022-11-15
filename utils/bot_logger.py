from __future__ import annotations
from datetime import datetime, timezone
from typing import ClassVar, List, Optional

from utils.config import Config

import discord
from discord.utils import MISSING


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
    _logger: ClassVar[BotLogger] = MISSING

    def __init__(self) -> None:
        # attributi sono qua solo per dichiararli
        self.channel: Optional[discord.TextChannel]
        raise RuntimeError(
            'Usa BotLogger.create_instance per istanziare il logger')

    @classmethod
    def create_instance(cls, bot) -> BotLogger:
        """Crea e ritorna l'istanza del logger e ne inizializza gli attributi.

        :param bot: il bot
        """
        if cls._logger is MISSING:
            cls._logger = cls.__new__(cls)
            cls._logger.channel = None
        return cls._logger

    @classmethod
    def get_instance(cls) -> BotLogger:
        """Ritorna l'unica istanza del logger."""
        return cls._logger

    async def initialize(self) -> None:
        """Inizializza il logger caricando il canale dedicato. La chiamata
        a questo metodo deve essere fatta una volta sola prima che il logger
        possa procedere con il logging.
        """
        self.channel = Config.get_config().log_channel

    async def log(self,  msg: str, media: Optional[List[discord.Attachment]] = None) -> None:
        """Compila il messaggio da inviare nel canale. Il formato
        è il seguente:

        YYYY-MM-DD HH:MM:SS.DDDDDD  <msg>

        La data arriva da datetime.now()

        :param msg: il messaggio con l'evento da loggare
        :param media: eventuali allegati del messaggio (immagini, video, etc)
        """
        timestamp = datetime.now()
        if self.channel is None:
            # fallback sul terminale
            print(f'[{timestamp}]:\n{msg}')
            return
        msg = f'`{timestamp}`\n{msg}'
        log_message = discord.Embed(
            title='Log event',
            description=msg,
            # Il timestamp dell'embed è regolato da discord, lo converto in UTC
            timestamp=timestamp.astimezone(timezone.utc)
        )
        files: List[discord.File] = [await m.to_file() for m in media] if media else []
        await self.channel.send(embed=log_message, files=files)
