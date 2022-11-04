"""bot.py"""
from __future__ import annotations
from aflbot import AFLBot
import os
import logging

import discord
from dotenv import load_dotenv
from utils.archive import Archive
from utils.banned_words import BannedWords
from utils.bot_logger import BotLogger
from utils.config import Config

# logging di base sul terminale
logging.basicConfig(level=logging.INFO)

# carico il token dal .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
assert TOKEN is not None, 'Il token non è stato trovato'

# carica la configurazione, ricorda di modificare config.json seguendo indicazioni del template
if not Config.get_config():
    print('controlla di avere creato correttamente config.json')
    exit()
# carica le parole bannate
BannedWords.load()
# carica l'archivio dati
Archive.load_archive()

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
try:
    bot.run(TOKEN)
except AssertionError as e:
    print('configurazione del bot non valida:', e)
    exit()
