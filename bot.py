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

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

#modificare config.json prima di avviare il bot
with open('config.json', 'r') as file:
    config = json.load(file)
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

#parole bannate
try:
    with open('banned_words.json','r') as file:
        banned_words = json.load(file)
except (FileNotFoundError, json.decoder.JSONDecodeError):
    with open('banned_words.json','w+') as file:
        banned_words = []

weekdays = {
    0: "mon",
    1: "tue",
    2: "wed",
    3: "thu",
    4: "fri",
    5: "sat",
    6: "sun"
}

#per poter ricevere le notifiche sull'unione di nuovi membri
intents = discord.Intents.default()
intents.members = True

#istanziare il bot (avvio in fondo al codice)
bot = commands.Bot(command_prefix = CURRENT_PREFIX, intents=intents)

@bot.event
async def on_ready():
    timestamp = datetime.time(datetime.now())
    print(f'{bot.user} has connected to Discord! 'f'{timestamp}')
    if(MAIN_CHANNEL_ID is not None):
        channel = bot.get_channel(MAIN_CHANNEL_ID)
        await channel.send('Bot avviato alle 'f'{timestamp}. Il prefisso è: {bot.command_prefix}')
        periodic_checks.start()

@bot.event
async def on_message(message):
    if message.author == bot.user or message.author.bot:  #non conta sé stesso e gli altri bot
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

    if message.content == 'greta':
        await message.channel.send(greetings)
        return
    
    if contains_banned_words(message.content) and message.channel.id not in EXCEPTIONAL_CHANNELS_ID:
        await message.delete()
        await warn(message.author, "linguaggio inappropriato")
        return

    if message.author.id not in MODERATION_ROLES_ID:
        update_counter(message)

    #istruzione necessaria per processare i messaggi come comandi.
    await bot.process_commands(message)
    #escludere i comandi da update_counter?

@bot.event
async def on_message_delete(message):
    """In caso di rimozione dei messaggi va decrementato il contatore della persona che
    lo aveva scritto per evitare che messaggi non adatti vengano conteggiati nell'assegnamento del ruolo.
    """
    try:
       with open('aflers.json','r') as file:
            prev_dict = json.load(file)
    except FileNotFoundError:
        return
    try:
        d = prev_dict.get(str(message.author.id))
    except KeyError:
        print('utente non presente')
        return
    #il contatore non può ovviamente andare sotto 0
    if d[weekdays.get(datetime.today().weekday())] != 0:
        d[weekdays.get(datetime.today().weekday())] -= 1
        update_json_file(prev_dict, 'aflers.json')
        print('rimosso un messaggio')

@bot.event
async def on_reaction_add(reaction, user):
    """Controlla se chi reagisce ai messaggi ha i requisiti per farlo"""
    if reaction.message.channel.id == POLL_CHANNEL_ID:
        if bot.get_guild(GUILD_ID).get_role(ACTIVE_ROLE_ID) not in user.roles:
            for role in user.roles:
                if role.id not in MODERATION_ROLES_ID:
                    await reaction.remove(user)

@bot.event
async def on_message_edit(before, after):
    """"Controlla che i messaggi non vengano editati per inserire parole della lista banned_words"""
    if (contains_banned_words(after)):
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
    if contains_banned_words(member.display_name):
        await member.kick(reason="ForbiddenUsername")
        await channel.send(f'Il tuo username non è consentito, ritenta l\'accesso dopo averlo modificato')

@bot.event
async def on_member_remove(member):
    """rimuove l'utente da aflers.json"""
    if member.bot:
        return
    with open('aflers.json','w+') as file:
        prev_dict = json.load(file)
        try:
            del prev_dict[str(member.id)]
            json.dump(data, file, indent=4)
        except KeyError:
            return

@bot.event
async def on_member_update(before, after):
    """controlla che chi è entrato e ha modificato il nickname ne abbia messo uno adeguato"""
    guild = bot.get_guild(GUILD_ID)
    if contains_banned_words(after.display_name):
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

@bot.command()
async def blackadd(ctx, ban_word):
    """Aggiunge stringhe alla lista contenuta in banned_words.json.
    Se la parola è composta da più parole separate da uno spazio, va messa tra ""
    """
    if ctx.author.top_role.id not in MODERATION_ROLES_ID:
        return
    if ban_word in banned_words:
        await ctx.send(f'la parola è già contenuta nell\'elenco')
        return
    banned_words.append(ban_word)
    update_json_file(banned_words, 'banned_words.json')
    await ctx.send(f'parola aggiunta correttamente')

@bot.command()
async def blackremove(ctx, ban_word):
    """elimina una banned_word dall'elenco"""
    if ctx.author.top_role.id not in MODERATION_ROLES_ID:
        return
    if ban_word in banned_words:
        banned_words.remove(ban_word)
        update_json_file(banned_words, 'banned_words.json')
        await ctx.send(f'la parola è stata rimossa')
    else:
        await ctx.send(f'la parola non è presente nell\'elenco')

@bot.command()
async def setprefix(ctx, prefix):
    """imposta prefix come nuovo prefisso del bot"""
    if ctx.author.top_role.id not in MODERATION_ROLES_ID:
        return
    bot.command_prefix = prefix
    os.putenv('CURRENT_PREFIX', prefix)
    await ctx.send(f'Prefisso cambiato in ``{prefix}``')

@bot.command()
async def hello(ctx):
    """comando di prova, che ti saluta in una lingua diversa dalla tua"""
    await ctx.send(f'ciao {ctx.author.display_name}')

@tasks.loop(minutes=1)
async def periodic_checks():
    """Task periodica per la gestione di:
           - assegnamento ruolo attivo
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
        item = prev_dict.get(key)
        count = count_messages(item)
        if count >= ACTIVE_THRESHOLD:
            #nota: non serve fare distinzione tra coloro che sono già attivi e coloro che 
            #rinnovano il ruolo perchè in entrambi i casi l'operazione da fare è la stessa
            item["active"] = True
            item["expiration"] = datetime.date(datetime.now() + timedelta(days=ACTIVE_DURATION)).__str__()
            guild = bot.get_guild(GUILD_ID)
            await guild.get_member(int(key)).add_roles(guild.get_role(ACTIVE_ROLE_ID))
            print('member ' + key + ' is active')
            channel = bot.get_channel(MAIN_CHANNEL_ID)
            await channel.send('membro ' + key + ' è diventato attivo')
            #azzero tutti i contatori
            for i in weekdays:
                item[weekdays.get(i)] = 0

        #controllo sulla data dell'ultima violazione, ed eventuale reset
        if item["last_violation_count"] is not None:
            expiration = datetime.date(datetime.strptime(item["last_violation_count"], '%Y-%m-%d'))
            if (expiration + timedelta(days=VIOLATIONS_RESET_DAYS)).__eq__(datetime.date(datetime.now())):
                print('reset violazioni di ' + key)
                item["violations_count"] = 0
                item["last_violation_count"] = None

        #rimuovo i messaggi contati 7 giorni fa
        item[weekdays.get(datetime.today().weekday())] = 0

        #pausa artificiale per controllare se il ruolo è assegnato durante i test
        print('aspetta 15 sec...')
        await asyncio.sleep(15)
        print('passati')

        if item["active"] is True:
            expiration = datetime.date(datetime.strptime(item["expiration"], '%Y-%m-%d'))
            channel = bot.get_channel(MAIN_CHANNEL_ID)
            check = (datetime.date(datetime.now()) + timedelta(days=ACTIVE_DURATION))
            await channel.send('expire = ' + expiration.__str__() + ' check = ' + check.__str__())
            if expiration.__eq__((datetime.date(datetime.now()) + timedelta(days=ACTIVE_DURATION))): #prova per vedere se va
                guild = bot.get_guild(GUILD_ID)
                await guild.get_member(int(key)).remove_roles(guild.get_role(ACTIVE_ROLE_ID))
                await channel.send('membro ' + key + ' non più attivo :(')
                item["active"] = False
                item["expiration"] = None
    update_json_file(prev_dict, 'aflers.json')

def update_counter(message):
    """Aggiorna il contatore dell'utente che ha mandato il messaggio. Se l'utente non era presente lo aggiunge
    al json inizializzando tutti i contatori a 0
    """
    if  not does_it_count(message):
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
            d = prev_dict.get(key)
            #incrementa solo il campo corrispondente al giorno corrente
            d[weekdays.get(datetime.today().weekday())] += 1
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
                "violations_count": 0,
                "last_violation_count": None,
                "active": False,
                "expiration": None
            }
            afler[weekdays.get(datetime.today().weekday())] = 1
            prev_dict[message.author.id] = afler
        update_json_file(prev_dict, 'aflers.json')

def does_it_count(message):
    """Controlla se il messaggio ricevuto rispetta le condizioni per essere conteggiato ai fini del ruolo attivo"""
    if message.guild is not None:
        if message.guild.id == GUILD_ID:
            if message.channel.id in ACTIVE_CHANNELS_ID:
                print('counts')
                return True
        print('doesn\'t count')
    return False

def update_json_file(data, json_file):
    """Scrive su file le modifiche apportate all' archivio json con il conteggio dei messaggi"""
    with open(json_file, 'w') as file:
        json.dump(data, file, indent=4)

def count_messages(item):
    """Ritorna il conteggio totale dei messaggi dei 7 giorni precedenti"""
    count = 0
    for i in weekdays:
        count += item[weekdays.get(i)]
    return count

def contains_banned_words(text):
    """Implementa il controllo sulle parole bannate tramite regex"""
    text_to_check = text.lower()
    text_to_check = re.sub("0", "o", text_to_check)
    text_to_check = re.sub("1", "i", text_to_check)
    text_to_check = re.sub("5", "s", text_to_check)
    text_to_check = re.sub("2", "z", text_to_check)
    text_to_check = re.sub("8", "b", text_to_check)
    text_to_check = re.sub("4", "a", text_to_check)
    text_to_check = re.sub("3", "e", text_to_check)
    text_to_check = re.sub("7", "t", text_to_check)
    for word in banned_words:
        regex_word = "+ *\W*".join(word)
        x = re.search(regex_word, text_to_check)
        if x is not None:
            return True
    return False

async def warn(member, reason):
    """incrementa il numero di violazioni e tiene traccia della prima violazione commesa"""
    prev_dict = {}
    penalty = "warnato."
    try:
        with open('aflers.json','r') as file:
            prev_dict = json.load(file)
    except FileNotFoundError:
        print('file non trovato, lo creo ora')
        with open('aflers.json','w+') as file:
            prev_dict = {}
    finally:
        key = str(member.id)
        if key in prev_dict:
            d = prev_dict.get(key)
            if d["violations_count"] == 2:
                await member.add_roles(bot.get_guild(GUILD_ID).get_role(UNDER_SURVEILLANCE_ID))
                penalty = "sottoposto a sorveglianza, il prossimo sara' un ban."
            elif d["violations_count"] == 3:
                k = reason
                await member.ban(delete_message_days = 0, reason = k)
                penalty = "bannato dal server."
            d["last_violation_count"] = datetime.date(datetime.now()).__str__()
            d["violations_count"] += 1
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
                "violations_count": 1,
                "last_violation_count": datetime.date(datetime.now()).__str__(),
                "active": False,
                "expiration": None
            }
            prev_dict[key] = afler
        channel = await member.create_dm()
        await channel.send("Sei stato " + penalty + " Motivo: " + reason + ".")
        update_json_file(prev_dict, 'aflers.json')

bot.run(TOKEN)
