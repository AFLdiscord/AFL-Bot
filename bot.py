# bot.py
import os
import json
import asyncio
import re

import discord
from discord.ext import tasks
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime, timedelta
from cogs import sharedFunctions

__version__ = 'v0.3.1'

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

#modificare config.json prima di avviare il bot
try:
   with open('config.json', 'r') as file:
       config = json.load(file)
except FileNotFoundError:
    print('crea il file config.json seguendo le indicazioni del template')
    exit()
GUILD_ID = int(config['guild_id'])
MAIN_CHANNEL_ID = int(config['main_channel_id'])
CURRENT_PREFIX = config['current_prefix']
MODERATION_ROLES_ID = []
for mod in config['moderation_roles_id']:
    MODERATION_ROLES_ID.append(int(mod))
ACTIVE_ROLE_ID = int(config['active']['role_id'])
ACTIVE_CHANNELS_ID = []
for channel in config['active']['channels_id']:
    ACTIVE_CHANNELS_ID.append(int(channel))
ACTIVE_THRESHOLD = config['active']['threshold']
ACTIVE_DURATION = config['active']['duration']
EXCEPTIONAL_CHANNELS_ID = []
for channel in config['exceptional_channels_id']:
    EXCEPTIONAL_CHANNELS_ID.append(int(channel))
POLL_CHANNEL_ID = int(config['poll_channel_id'])
UNDER_SURVEILLANCE_ID = int(config['under_surveillance_id'])
VIOLATIONS_RESET_DAYS = config["violations_reset_days"]
greetings = config['greetings']

#salva le parole bannate
b = sharedFunctions.BannedWords()

#per poter ricevere le notifiche sull'unione di nuovi membri e i ban
intents = discord.Intents.default()
intents.members = True
intents.bans = True

#istanziare il bot (avvio in fondo al codice)
bot = commands.Bot(command_prefix = CURRENT_PREFIX, intents=intents)

#carico i moduli dei comandi
extensions = [
    'cogs.ModerationCog',
    'cogs.ConfigCog',
    'cogs.UtilityCog',
    'cogs.EventsCog'
]
for ext in extensions:
    bot.load_extension(ext)

async def is_mod(ctx):
    """check sui comandi per bloccare l'utilizzo dei comandi di moderazione"""
    #TODO spostare le funzioni di check nello stesso posto
    return ctx.author.top_role.id in MODERATION_ROLES_ID

@bot.command()
@commands.check(is_mod)
async def reload(ctx):
    """ricarica tutte le cogs aggiornando le funzionalità"""
    try:
        for ext in extensions:
            bot.reload_extension(ext)
        await ctx.send("Estensioni ricaricate correttamente")
    except Exception as e:
        print(e)
        await ctx.send("Errore nella ricarica dei moduli, vedi log del bot", delete_after=5)
        await ctx.message.delete(delay=5)

@bot.event
async def on_ready():
    timestamp = datetime.time(datetime.now())
    botstat = discord.Game(name='AFL ' + __version__)
    await bot.change_presence(activity=botstat)
    print(f'{bot.user} has connected to Discord! 'f'{timestamp}')
    if(MAIN_CHANNEL_ID is not None):
        channel = bot.get_channel(MAIN_CHANNEL_ID)
        await channel.send('AFL Bot `' + __version__ + '` avviato alle `'f'{timestamp}`. Il prefisso è: `{bot.command_prefix}`')
        periodic_checks.start()

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
        if count >= ACTIVE_THRESHOLD and bot.get_guild(GUILD_ID).get_member(int(key)).top_role.id not in MODERATION_ROLES_ID:
            item["active"] = True
            item["expiration"] = datetime.date(datetime.now() + timedelta(days=ACTIVE_DURATION)).__str__()
            guild = bot.get_guild(GUILD_ID)
            await guild.get_member(int(key)).add_roles(guild.get_role(ACTIVE_ROLE_ID))
            print('member ' + key + ' is active')
            channel = bot.get_channel(MAIN_CHANNEL_ID)
            await channel.send('membro <@!' + key + '> è diventato attivo')
            #azzero tutti i contatori
            for i in sharedFunctions.weekdays:
                item[sharedFunctions.weekdays.get(i)] = 0

        #controllo sulla data dell'ultima violazione, ed eventuale reset
        if item["last_violation_count"] is not None:
            expiration = datetime.date(datetime.strptime(item["last_violation_count"], '%Y-%m-%d'))
            if (expiration + timedelta(days=VIOLATIONS_RESET_DAYS)).__eq__(datetime.date(datetime.now())):
                print('reset violazioni di ' + key)
                item["violations_count"] = 0
                item["last_violation_count"] = None

        #rimuovo i messaggi contati 7 giorni fa
        item[sharedFunctions.weekdays.get(datetime.today().weekday())] = 0

        if item["active"] is True:
            expiration = datetime.date(datetime.strptime(item["expiration"], '%Y-%m-%d'))
            channel = bot.get_channel(MAIN_CHANNEL_ID)
            if expiration.__eq__((datetime.date(datetime.now()))):
                guild = bot.get_guild(GUILD_ID)
                await guild.get_member(int(key)).remove_roles(guild.get_role(ACTIVE_ROLE_ID))
                await channel.send('membro ' + key + ' non più attivo :(')
                item["active"] = False
                item["expiration"] = None
    sharedFunctions.update_json_file(prev_dict, 'aflers.json')

bot.run(TOKEN)
