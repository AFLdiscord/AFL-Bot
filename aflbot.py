from datetime import datetime

from discord.ext import commands
from utils.shared_functions import get_extensions

class AFLBot(commands.Bot):
    """Istanza del bot. Rispetto a commands.Bot ha le seguenti
    informazioni aggiuntive:

    - version: str           tiene traccia della versione
    - start_time: datetime   timestamp di avvio del bot
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.version: str
        self.start_time: datetime

    # carico i moduli dei comandi
    async def setup_hook(self) -> None:
        for ext in get_extensions():
            await self.load_extension(ext)
