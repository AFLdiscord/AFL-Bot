"""bot.py"""
import os
import asyncio
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv
from utils import shared_functions
from utils.shared_functions import Archive, BannedWords, BotLogger, Config

# logging di base sul terminale
logging.basicConfig(level=logging.INFO)

# carico il token dal .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
assert TOKEN is not None

# carica la configurazione, ricorda di modificare config.json seguendo indicazioni del template
if not Config.get_config():
    print('controlla di avere creato correttamente config.json')
    exit()
# carica le parole bannate
BannedWords.load()
# carica l'archivio dati
Archive.load_archive()

# bot


class AFLBot(commands.Bot):

    # carico i moduli dei comandi
    async def setup_hook(self) -> None:
        extensions = shared_functions.get_extensions()
        for ext in extensions:
            await bot.load_extension(ext)


# per poter ricevere le notifiche sull'unione di nuovi membri e i ban
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# istanziare il bot (avvio in fondo al codice)
bot = AFLBot(
    command_prefix=Config.get_config().current_prefix, intents=intents)

# setup del logging nel canale dedicato
logger = BotLogger.create_instance(bot)

# lancio il bot
bot.run(TOKEN)
