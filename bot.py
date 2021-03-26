# bot.py
import os
import json
import asyncio
import re
import logging

import discord
from discord.ext import tasks
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime, timedelta
from cogs import sharedFunctions
from cogs.sharedFunctions import BannedWords, Config

__version__ = 'v0.4'

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

@bot.event
async def on_ready():
    timestamp = datetime.time(datetime.now())
    botstat = discord.Game(name='AFL ' + __version__)
    await bot.change_presence(activity=botstat)
    print(f'{bot.user} has connected to Discord! 'f'{timestamp}')
    if(Config.config['main_channel_id'] is not None):
        channel = bot.get_channel(Config.config['main_channel_id'])
        await channel.send('AFL Bot `' + __version__ + '` avviato alle `'f'{timestamp}`. Il prefisso è: `{bot.command_prefix}`')
    if not periodic_checks.is_running():    #per evitare RuntimeExceptions se il bot si disconnette per un periodo prolungato
        print('avvio task')
        periodic_checks.start()
    else:
        print('task già avviata')

@tasks.loop(hours=24)
async def periodic_checks():
    """Task periodica per la gestione di:
           - assegnamento ruolo attivo (i mod sono esclusi)
           - rimozione ruolo attivo
           - rimozione strike/violazioni

        L'avvio è programmato ogni giorno allo scatto della mezzanotte.
    """
    print('controllo conteggio messaggi')
    try:
        with open('aflers.json','r') as file:
            prev_dict = json.load(file)
    except FileNotFoundError:
        return
    for key in prev_dict:
        item = prev_dict[key]
        sharedFunctions.clean(item)
        count = sharedFunctions.count_consolidated_messages(item)
        if count >= Config.config['active_threshold'] and bot.get_guild(Config.config['guild_id']).get_member(int(key)).top_role.id not in Config.config['moderation_roles_id']:
            item["active"] = True
            item["expiration"] = datetime.date(datetime.now() + timedelta(days=Config.config['active_duration'])).__str__()
            guild = bot.get_guild(Config.config['guild_id'])
            await guild.get_member(int(key)).add_roles(guild.get_role(Config.config['active_role_id']))
            print('member ' + key + ' is active')
            channel = bot.get_channel(Config.config['main_channel_id'])
            await channel.send('membro <@!' + key + '> è diventato attivo')
            #azzero tutti i contatori
            for i in sharedFunctions.weekdays:
                item[sharedFunctions.weekdays.get(i)] = 0

        #controllo sulla data dell'ultima violazione, ed eventuale reset
        if item["last_violation_count"] is not None:
            expiration = datetime.date(datetime.strptime(item["last_violation_count"], '%Y-%m-%d'))
            if (expiration + timedelta(days=Config.config["violations_reset_days"])).__eq__(datetime.date(datetime.now())):
                print('reset violazioni di ' + key)
                item["violations_count"] = 0
                item["last_violation_count"] = None

        #rimuovo i messaggi contati 7 giorni fa
        item[sharedFunctions.weekdays.get(datetime.today().weekday())] = 0

        if item["active"] is True:
            expiration = datetime.date(datetime.strptime(item["expiration"], '%Y-%m-%d'))
            channel = bot.get_channel(Config.config['main_channel_id'])
            if expiration.__eq__((datetime.date(datetime.now()))):
                guild = bot.get_guild(Config.config['guild_id'])
                await guild.get_member(int(key)).remove_roles(guild.get_role(Config.config['active_role_id']))
                await channel.send('membro ' + key + ' non più attivo :(')
                item["active"] = False
                item["expiration"] = None
    sharedFunctions.update_json_file(prev_dict, 'aflers.json')

bot.run(TOKEN)
