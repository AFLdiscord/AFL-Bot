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

__version__ = '0.2.1'

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

#per poter ricevere le notifiche sull'unione di nuovi membri e i ban
intents = discord.Intents.default()
intents.members = True
intents.bans = True

#istanziare il bot (avvio in fondo al codice)
bot = commands.Bot(command_prefix = CURRENT_PREFIX, intents=intents)

@bot.event
async def on_ready():
    timestamp = datetime.time(datetime.now())
    botstat = discord.Game(name='AFL')
    await bot.change_presence(activity=botstat)
    print(f'{bot.user} has connected to Discord! 'f'{timestamp}')
    if(MAIN_CHANNEL_ID is not None):
        channel = bot.get_channel(MAIN_CHANNEL_ID)
        await channel.send('AFL Bot ' + __version__ + ' avviato alle 'f'{timestamp}. Il prefisso è: {bot.command_prefix}')
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
    
    if contains_banned_words(message.content) and message.channel.id not in EXCEPTIONAL_CHANNELS_ID:
        await message.delete()
        await add_warn(message.author, 'linguaggio inappropriato', 1)
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
    if d[weekdays.get(datetime.today().weekday())] != 0:
        d[weekdays.get(datetime.today().weekday())] -= 1
        update_json_file(prev_dict, 'aflers.json')
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
    if (contains_banned_words(after.content)):
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
    update_json_file(prev_dict, 'aflers.json')

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

async def is_mod(ctx):
    """check sui comandi per bloccare l'utilizzo dei comandi di moderazione"""
    return ctx.author.top_role.id in MODERATION_ROLES_ID

@bot.command()
@commands.check(is_mod)
async def blackadd(ctx, ban_word):
    """Aggiunge stringhe alla lista contenuta in banned_words.json.
    Se la parola è composta da più parole separate da uno spazio, va messa tra ""
    """
    if ban_word in banned_words:
        await ctx.send(f'la parola è già contenuta nell\'elenco')
        return
    banned_words.append(ban_word)
    update_json_file(banned_words, 'banned_words.json')
    await ctx.send(f'parola aggiunta correttamente', delete_after=5)

@bot.command()
@commands.check(is_mod)
async def blackremove(ctx, ban_word):
    """elimina una banned_word dall'elenco"""
    if ban_word in banned_words:
        banned_words.remove(ban_word)
        update_json_file(banned_words, 'banned_words.json')
        await ctx.send(f'la parola è stata rimossa', delete_after=5)
    else:
        await ctx.send(f'la parola non è presente nell\'elenco', delete_after=5)

@bot.command(aliases=['black', 'bl'])
@commands.check(is_mod)
async def blacklist(ctx):
    """stampa l'elenco delle parole attualmente bannate"""
    string = ''
    for w in banned_words:
        string += w + '\n'
    await ctx.send(string)

@bot.command()
@commands.check(is_mod)
async def setprefix(ctx, prefix):
    """imposta prefix come nuovo prefisso del bot"""
    bot.command_prefix = prefix
    await ctx.send(f'Prefisso cambiato in ``{prefix}``')

@bot.command()
@commands.check(is_mod)
async def warn(ctx, attempted_member=None, *, reason='un moderatore ha ritenuto inopportuno il tuo comportamento'):
    """aggiunge un warn all'utente menzionato nel messaggio (basta il nome)
    L'effetto è il seguente:
    - aggiunge un warn all'autore del messaggio a cui si risponde/utente menzionato
    - cancella il messaggio citato (se presente)
    - cancella il comando di warn
    """
    if attempted_member is None:   #nessun argomento passato al warn
        if ctx.message.reference is None:
            #sono in questo caso quando mando <warn da solo
            await ctx.send("Devi menzionare qualcuno o rispondere a un messaggio per poter usare questo comando", delete_after=5)
            return
        else:
            #in questo caso ho risposto a un messaggio con <warn
            msg = await ctx.fetch_message(ctx.message.reference.message_id)
            member = msg.author
            await msg.delete()
    else:   #con argomenti al warn
        if not ctx.message.mentions:   #nessuna menzione nel messaggio
            await ctx.send("Devi menzionare qualcuno o rispondere a un messaggio per poter usare questo comando", delete_after=5)
            return
        else:
            if ctx.message.reference is None:
                #ho chiamato il warn a mano <warn @somebody ragione
                member = ctx.message.mentions[0]
            else:
                #ho menzionato qualcuno, prendo come target del warn
                msg = await ctx.fetch_message(ctx.message.reference.message_id)
                member = msg.author
                await msg.delete()
                #solo se vado per reference devo sistemare la reason perchè la prima parola va in attempted_member
                if reason == 'un moderatore ha ritenuto inopportuno il tuo comportamento':
                    reason = attempted_member   #ragione di una sola parola, altrimenti poi concatena tutto
                else:
                    reason = attempted_member + ' ' + reason  #devo inserire uno spazio altrimenti scrive tutto appicciato
    if member.bot or member == ctx.author:
        return
    await add_warn(member, reason, 1)
    user = '<@!' + str(member.id) + '>'
    await ctx.send(user + ' warnato. Motivo: ' + reason)
    await ctx.message.delete(delay=5)   

@bot.command()
@commands.check(is_mod)
async def unwarn(ctx, member: discord.Member):
    """rimuove un warn all'utente menzionato"""
    if member.bot:
        return
    reason = 'buona condotta'
    await add_warn(member, reason, -1)
    user = '<@!' + str(member.id) + '>'
    await ctx.send(user + ' rimosso un warn.')
    await ctx.message.delete(delay=5)

@bot.command(aliases=['warnc', 'wc'])
@commands.check(is_mod)
async def warncount(ctx):
    """stampa nel canale in cui viene chiamato l'elenco di tutti i warn degli utenti."""
    try:
        with open('aflers.json','r') as file:
            prev_dict = json.load(file)
    except FileNotFoundError:
        await ctx.send('nessuna attività registrata', delete_after=5)
        await ctx.message.delete(delay=5)
        return
    warnc = ''
    for user in prev_dict:
        name = bot.get_guild(GUILD_ID).get_member(int(user)).display_name
        item = prev_dict[user]
        count = str(item["violations_count"])
        msg = name + ': ' + count + ' warn\n'
        warnc += msg
    await ctx.send(warnc)

@bot.command()
async def status(ctx, member:discord.Member = None):
    """mostra il proprio status oppure quello del membro fornito come parametro"""
    if member is None:
        member = ctx.author
    try:
        with open('aflers.json','r') as file:
            prev_dict = json.load(file)
    except FileNotFoundError:
        await ctx.send('nessun elenco', delete_after=5)
        await ctx.message.delete(delay=5)
        return
    try:
        item = prev_dict[str(member.id)]
    except KeyError:
        print('non presente')
        await ctx.send('l\'utente indicato non è registrato', delete_after=5)
        await ctx.message.delete(delay=5)
        return
    status = discord.Embed(
        title=f'Status di {member.display_name}',
        color=member.top_role.color
    )
    status.set_thumbnail(url=member.avatar_url)
    status.add_field(name='Messaggi ultimi 7 giorni:', value=str(count_messages(item)), inline=False)
    is_a_mod = False
    for role in member.roles:
        if role.id in MODERATION_ROLES_ID:
            is_a_mod = True
            status.add_field(name='Ruolo:', value=role.name, inline=False)
            break
    if not is_a_mod:
        if item["active"] == False:
            status.add_field(name='Attivo:', value='no', inline=False)
        else:
            status.add_field(name='Attivo:', value='sì (scade il ' + item["expiration"] + ')', inline=False)
    if item["violations_count"] == 0:
        status.add_field(name='Violazioni:', value='0', inline=False)
    else:
        violations_expiration = datetime.date(datetime.strptime(item["last_violation_count"], '%Y-%m-%d') +
            timedelta(days=VIOLATIONS_RESET_DAYS)).__str__()
        status.add_field(name='Violazioni:', value=str(item["violations_count"]) +
            ' (scade il ' + violations_expiration + ')', inline=False)
    await ctx.send(embed=status)

@bot.command()
async def avatar(ctx, user: discord.User = None):
    """invia sulla chat la pfp dell'utente menzionato, indipendentemente dal fatto che l'utente sia
    un membro del server o meno
    """
    if user is None:
        user = ctx.author
    #se l'utente è nel server, stampo il suo nickname invece del suo username
    member = bot.get_guild(GUILD_ID).get_member(user.id)
    if member is not None:
        user = member
    avatar = discord.Embed(
        title=f'Avatar di {user.display_name}:'
    )
    avatar.set_image(url=user.avatar_url)
    await ctx.send(embed=avatar)

@bot.command()
@commands.check(is_mod)
async def ban(ctx, member: discord.Member = None, *, reason='un moderatore ha ritenuto inopportuno il tuo comportamento'):
    """banna un membro dal server"""
    if member is None:
        await ctx.send('specifica un membro da bannare', delete_after=5)
        await ctx.message.delete(delay=5)
        return
    user = '<@!' + str(member.id) + '>'
    await ctx.send(user + ' bannato. Motivo: ' + reason)
    await ctx.message.delete(delay=5)
    penalty = 'bannato dal server.' 
    channel = await member.create_dm()
    await channel.send('Sei stato ' + penalty + ' Motivo: ' + reason + '.')
    await member.ban(delete_message_days = 0, reason = reason)

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
        count = count_messages(item)
        if count >= ACTIVE_THRESHOLD and bot.get_guild(GUILD_ID).get_member(int(key)).top_role.id not in MODERATION_ROLES_ID:
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

        if item["active"] is True:
            expiration = datetime.date(datetime.strptime(item["expiration"], '%Y-%m-%d'))
            channel = bot.get_channel(MAIN_CHANNEL_ID)
            if expiration.__eq__((datetime.date(datetime.now()))):
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
                return True
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
    text_to_check = re.sub("9", "g", text_to_check)
    for word in banned_words:
        regex_word = '+ *\W*'.join(word)
        x = re.search(regex_word, text_to_check)
        if x is not None:
            return True
    return False

async def add_warn(member, reason, number):
    """incrementa o decremente il numero di violazioni di numero e tiene traccia dell'ultima violazione commessa"""
    prev_dict = {}
    penalty = 'warnato.'
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
            d = prev_dict[key]
            d["violations_count"] += number
            d["last_violation_count"] = datetime.date(datetime.now()).__str__()
            update_json_file(prev_dict, 'aflers.json')
            if d["violations_count"] <= 0:
                d["violations_count"] = 0
                d["last_violation_count"] = None
                update_json_file(prev_dict, 'aflers.json')
                return
            if number < 0:  #non deve controllare se è un unwarn
                return
            if d["violations_count"] == 3:
                await member.add_roles(bot.get_guild(GUILD_ID).get_role(UNDER_SURVEILLANCE_ID))
                penalty = 'sottoposto a sorveglianza, il prossimo sara\' un ban.'
                channel = await member.create_dm()
                update_json_file(prev_dict, 'aflers.json')
                await channel.send('Sei stato ' + penalty + ' Motivo: ' + reason + '.')
            elif d["violations_count"] >= 4:
                penalty = 'bannato dal server.' 
                channel = await member.create_dm()
                await channel.send('Sei stato ' + penalty + ' Motivo: ' + reason + '.')
                update_json_file(prev_dict, 'aflers.json')
                await member.ban(delete_message_days = 0, reason = reason)   
            else:
                channel = await member.create_dm()
                update_json_file(prev_dict, 'aflers.json')
                await channel.send('Sei stato ' + penalty + ' Motivo: ' + reason + '.')
        else:
            #contatore per ogni giorno per ovviare i problemi discussi nella issue #2
            if number < 0:
                return
            afler = {
                "mon": 0,
                "tue": 0,
                "wed": 0,
                "thu": 0,
                "fri": 0,
                "sat": 0,
                "sun": 0,
                "violations_count": number,
                "last_violation_count": datetime.date(datetime.now()).__str__(),
                "active": False,
                "expiration": None
            }
            prev_dict[key] = afler
            update_json_file(prev_dict, 'aflers.json')

bot.run(TOKEN)
