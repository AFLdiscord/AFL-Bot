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

__version__ = 'v0.3'

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
    'cogs.UtilityCog'
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
    botstat = discord.Game(name='AFL')
    await bot.change_presence(activity=botstat)
    print(f'{bot.user} has connected to Discord! 'f'{timestamp}')
    if(MAIN_CHANNEL_ID is not None):
        channel = bot.get_channel(MAIN_CHANNEL_ID)
        await channel.send('AFL Bot `' + __version__ + '` avviato alle `'f'{timestamp}`. Il prefisso è: `{bot.command_prefix}`')
        periodic_checks.start()

@bot.event
async def on_message(message):
    """azioni da eseguire ad ogni messaggio"""
    if message.author == bot.user or message.author.bot or message.guild is None:
        return

    if message.content.lower() == 'ping':
        response = 'pong in ' f'{round(bot.latency * 1000)} ms'
        await message.channel.send(response)
        return

    if (message.content == '69' or
        message.content == '420'):
        response = 'nice'
        await message.channel.send(response)
        return
    
    if sharedFunctions.BannedWords.contains_banned_words(message.content) and message.channel.id not in EXCEPTIONAL_CHANNELS_ID:
        #cancellazione e warn fatto nella cog ModerationCog, qua serve solo per non contare il messaggio
        return

    update_counter(message)

    #istruzione necessaria per processare i messaggi come comandi.
    await bot.process_commands(message)

@bot.event
async def on_message_delete(message):
    """In caso di rimozione dei messaggi va decrementato il contatore della persona che
    lo aveva scritto per evitare che messaggi non adatti vengano conteggiati nell'assegnamento del ruolo.
    Vanno considerate le cancellazioni solo dai canali conteggiati.
    """
    if message.author == bot.user or message.author.bot or message.guild is None:
        return
    if not does_it_count(message):
        return
    try:
       with open('aflers.json','r') as file:
            prev_dict = json.load(file)
    except FileNotFoundError:
        return
    d = None
    try:
        d = prev_dict[str(message.author.id)]
    except KeyError:
        print('utente non presente')
        return
    finally:
        if d is None:
            return
    #il contatore non può ovviamente andare sotto 0
    if d[sharedFunctions.weekdays.get(datetime.today().weekday())] != 0:
        d[sharedFunctions.weekdays.get(datetime.today().weekday())] -= 1
        sharedFunctions.update_json_file(prev_dict, 'aflers.json')
        print('rimosso un messaggio')

@bot.event
async def on_raw_reaction_add(payload):
    """Controlla se chi reagisce ai messaggi ha i requisiti per farlo"""
    if payload.channel_id == POLL_CHANNEL_ID and payload.event_type == 'REACTION_ADD':
        if bot.get_guild(GUILD_ID).get_role(ACTIVE_ROLE_ID) not in payload.member.roles:
            for role in payload.member.roles:
                if role.id in MODERATION_ROLES_ID:
                    return
            try:
                message = await bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
                await message.remove_reaction(payload.emoji, payload.member)
            except discord.NotFound:
                print('impossibile trovare il messaggio o la reaction cercate')
                return

@bot.event
async def on_message_edit(before, after):
    """"Controlla che i messaggi non vengano editati per inserire parole della lista banned_words"""
    if (sharedFunctions.BannedWords.contains_banned_words(after.content)):
        await after.delete()

@bot.event
async def on_member_join(member):
    """Invia il messaggio di benvenuto al membro che si è appena unito al server e controlla che l'username
    sia adeguato
    """
    if member.bot:
        return
    print('nuovo membro')
    channel = await member.create_dm()
    await channel.send(greetings)
    if sharedFunctions.BannedWords.contains_banned_words(member.display_name):
        await member.kick(reason="ForbiddenUsername")
        await channel.send(f'Il tuo username non è consentito, ritenta l\'accesso dopo averlo modificato')

@bot.event
async def on_member_remove(member):
    """rimuove l'utente da aflers.json se questo esce dal server"""
    if member.bot:
        return
    with open('aflers.json','r') as file:
        prev_dict = json.load(file)
        try:
            del prev_dict[str(member.id)]
        except KeyError:
            print('utente non trovato')
            return
    sharedFunctions.update_json_file(prev_dict, 'aflers.json')

@bot.event
async def on_member_update(before, after):
    """controlla che chi è entrato e ha modificato il nickname ne abbia messo uno adeguato"""
    guild = bot.get_guild(GUILD_ID)
    if sharedFunctions.BannedWords.contains_banned_words(after.display_name):
        if before.nick is not None:
            print('ripristino nickname a ' + str(after.id))
            await guild.get_member(after.id).edit(nick=before.display_name)
        else:
            channel = await member.create_dm()
            await member.kick(reason="ForbiddenNickname")
            await channel.send(f'Il tuo nickname non è consentito, quando rientri impostane uno valido')

@bot.event
async def on_user_update(before, after):
    """controlla che gli utenti non cambino nome mostrato qualora cambiassero username"""
    guild = bot.get_guild(GUILD_ID)
    if after.display_name != before.display_name:
        print('cambio nickname')
        await guild.get_member(after.id).edit(nick=before.display_name)

@bot.event
async def on_command_error(ctx, error):
    """generica gestione errori per evitare crash banali, da espandare in futuro"""
    if isinstance(error, commands.CommandNotFound):
       print('comando non trovato (se hai prefisso < ogni menzione a inizio messaggio da questo errore)')
    elif isinstance(error, commands.CheckFailure):
        await ctx.send('non hai i permessi per usare questo comando', delete_after=5)
        await ctx.message.delete(delay=5)
    print(error)

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
        count = sharedFunctions.count_messages(item)
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

def update_counter(message):
    """aggiorna il contatore dell'utente che ha mandato il messaggio. Se l'utente non era presente lo aggiunge
    al json inizializzando tutti i contatori a 0. Si occupa anche di aggiornare il campo "last_message_date".
    """
    if not does_it_count(message):
        return
    prev_dict = {}
    try:
        with open('aflers.json','r') as file:
            prev_dict = json.load(file)
    except FileNotFoundError:
        print('file non trovato, lo creo ora')
        with open('aflers.json','w+') as file:
            prev_dict = {}   #dizionario per permettere di cercare dell'ID facilmente
    finally:
        key = str(message.author.id)
        if key in prev_dict:
            d = prev_dict[key]
            if d["last_message_date"] == datetime.date(datetime.now()).__str__():   
                #messaggi dello stesso giorno, continuo a contare
                d["counter"] += 1
            elif d["last_message_date"] is None:
                #può succedere in teoria se uno riceve un warn senza aver mai scritto un messaggio (tecnicamente add_warn lo prevede)
                #oppure se resetto il file a mano per qualche motivo
                d["counter"] = 1
                d["last_message_date"] = datetime.date(datetime.now()).__str__()
            else:
                #è finito il giorno, salva i messaggi di "counter" nel giorno corrispondente e aggiorna data ultimo messaggio
                day = sharedFunctions.weekdays[datetime.date(datetime.today() - timedelta(days=1)).weekday()]
                d[day] = counter   #ah ah D-day
                d["counter"] = 1
                d["last_message_date"] = datetime.date(datetime.now()).__str__()
        else:
            #contatore per ogni giorno per ovviare i problemi discussi nella issue #2
            afler = {
                "mon": 0,
                "tue": 0,
                "wed": 0,
                "thu": 0,
                "fri": 0,
                "sat": 0,
                "sun": 0,
                "counter": 1,
                "last_message_date": datetime.date(datetime.now()).__str__(),
                "violations_count": 0,
                "last_violation_count": None,
                "active": False,
                "expiration": None
            }
            prev_dict[message.author.id] = afler
        sharedFunctions.update_json_file(prev_dict, 'aflers.json')

def does_it_count(message):
    """controlla se il messaggio ricevuto rispetta le condizioni per essere conteggiato ai fini del ruolo attivo"""
    if message.guild is not None:
        if message.guild.id == GUILD_ID:
            if message.channel.id in ACTIVE_CHANNELS_ID:
                return True
    return False

bot.run(TOKEN)
