# bot.py
import os
import json
import asyncio
import re
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime, timedelta
from cogs import sharedFunctions
from cogs.sharedFunctions import BannedWords, Config

#logging di base sul terminale
logging.basicConfig(level=logging.INFO)

#carico il token dal .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

#carica la configurzione, ricorda di modificare config.json seguendo indicazioni del template
if not Config.load():
    print('controlla di avere creato correttamente config.json')
    exit()
#carica le parole bannate
BannedWords.load()

#per poter ricevere le notifiche sull'unione di nuovi membri e i ban
intents = discord.Intents.default()
intents.members = True
intents.bans = True

#istanziare il bot (avvio in fondo al codice)
bot = commands.Bot(command_prefix = Config.config['current_prefix'], intents=intents)

#carico i moduli dei comandi
extensions = sharedFunctions.get_extensions()
for ext in extensions:
    bot.load_extension(ext)

#lancio il bot
bot.run(TOKEN)