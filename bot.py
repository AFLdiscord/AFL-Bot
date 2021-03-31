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

logging.basicConfig(level=logging.INFO)
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
with open('extensions.json', 'r') as file:
    extensions = json.load(file)
for ext in extensions:
    bot.load_extension(ext)

async def is_mod(ctx):
    """check sui comandi per bloccare l'utilizzo dei comandi di moderazione"""
    #TODO spostare le funzioni di check nello stesso posto
    return ctx.author.top_role.id in Config.config['moderation_roles_id']

@bot.command()
@commands.check(is_mod)
async def reload(ctx, *args):
    """Ricarica le cogs specificate aggiornando le funzionalità. Se nessuna cog è specificata ricarica tutte.
    Sintassi:
    <reload                              #ricarica tutte le estensioni
    <reload ModerationCog                #ricarica solo ModerationCog
    <reload ModerationCog UtilityCog     #più cogs separate da spazi
    """
    if not args:
        cogs = extensions
    else:
        cogs = []
        for e in args:
            cogs.append('cogs.' + e)
    reloaded = ''
    for ext in cogs:
        try:
            bot.reload_extension(ext)
            reloaded += ext + ' ' 
        except Exception as e:
            print(e)
            await ctx.send('Errore nella ricarica di ' + ext + ' , vedi log del bot.', delete_after=5)
            await ctx.message.delete(delay=5)
    if reloaded.__len__ != 0:
        await ctx.send('Estensioni ' + reloaded + 'ricaricate correttamente.')

bot.run(TOKEN)