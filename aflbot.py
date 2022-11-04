from __future__ import annotations
from datetime import datetime
from typing import Any, ClassVar, Optional

import discord
from discord.utils import MISSING
from discord.ext import commands
from utils.shared_functions import get_extensions

class AFLBot(commands.Bot):
    """Istanza del bot. È un singleton e rispetto a commands.Bot ha le
    seguenti informazioni aggiuntive:
    - version: str           tiene traccia della versione
    - start_time: datetime   timestamp di avvio del bot
    """
    _bot: ClassVar[AFLBot] = MISSING

    def __init__(
        self,
        command_prefix: str,
        intents: discord.Intents,
        help_command: commands.HelpCommand = commands.DefaultHelpCommand(),
        tree_cls=discord.app_commands.CommandTree,
        description: Optional[str] = None,
        **options: Any) -> None:
        if AFLBot._bot is not MISSING:
            raise RuntimeError('Bot già istanziato, usa get_instance')
        super().__init__(
            command_prefix,
            tree_cls=tree_cls,
            help_command=help_command,
            description=description,
            intents=intents,
            **options)
        self.version: str
        self.start_time: datetime

    @classmethod
    def get_instance(cls) -> AFLBot:
        return cls._bot

    # carico i moduli dei comandi
    async def setup_hook(self) -> None:
        for ext in get_extensions():
            await self.load_extension(ext)