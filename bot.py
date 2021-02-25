# bot.py
import os
import json
import asyncio

import discord
from discord.ext import tasks
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

#nota, forse è meglio metterle in un file di configurazione diverso?
MAIN_CHANNEL = int(os.getenv('MAIN_CHANNEL'))
ACTIVE_THRESHOLD = int(os.getenv('ACTIVE_THRESHOLD'))
ACTIVE_DURATION = int(os.getenv('ACTIVE_DURATION'))
ACTIVE_ROLE_ID = int(os.getenv('ACTIVE_ROLE'))
GUILD_ID = int(os.getenv('GUILD_ID'))
REACTION_CHECK_CHANNEL_ID = int(os.getenv('REACTION_CHECK_CHANNEL_ID'))

#todo caricare da file la lista delle parole bannate all'avvio
banned_words = [
    'porco dio'
]
weekdays = {
    0: "mon",
    1: "tue",
    2: "wed",
    3: "thu",
    4: "fri",
    5: "sat",
    6: "sun"
}

#canali di cui tenere conto dei messaggi
active_channels_id = [
    MAIN_CHANNEL     #solo per finalità di testing, poi anche questo verrà caricato da file di config
]

#id delle persone aggiunte al file così da averlo pronto senza aprire il file ogni volta
tracked_people_id = []

#l'inizializzazione della lista serve a non perdere quali persone sono presenti nel file in
#caso di riavvio del bot
try:
    with open('aflers.json','r') as file:
        d = json.load(file)
        tracked_people_id.update(d.keys())
except FileNotFoundError:
        pass

#ovviamente anche questo verrà caricato da file all'avvio
greetings = """
Benvenuto/a sul server discord AFL! \n
Prima di iniziare a partecipare nel server presentati nel canale richiesta di afl indicando almeno
- sesso
- età
Ti invitiamo a leggere attentamente il regolamento del server, reperibile sul canale regole.
Per chiarimenti rivolgiti pure ai moderatori.
Buona permanenza!
"""

#per poter ricevere le notifiche sull'unione di nuovi membri
intents = discord.Intents.default()
intents.members = True

#istanziare il client (avvio in fondo al codice)
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    timestamp = datetime.time(datetime.now())
    print(f'{client.user} has connected to Discord! 'f'{timestamp}')
    if(MAIN_CHANNEL is not None):
        channel = client.get_channel(MAIN_CHANNEL)
        await channel.send('Bot avviato alle 'f'{timestamp}')
        periodic_checks.start()

@client.event
async def on_message(message):
    if message.author == client.user or message.author.bot:  #non conta sè stesso e gli altri bot
        return

    if message.content.lower() == 'ping':
        response = 'pong in ' f'{round(client.latency * 1000)} ms'
        await message.channel.send(response)
        return

    if message.content == '69' or message.content == '420':
        response = 'nice'
        await message.channel.send(response)
        return
    
    if contains_banned_words(message):
        await message.delete()
        return

    update_counter(message)

@client.event
async def on_message_delete(message):
    """In caso di rimozione dei messaggi va decrementato il contatore della persona che
    lo aveva scritto per evitare che messaggi non adatti vengano conteggiati nell'assegnamento del ruolo.
    """
    if message.author.id in tracked_people_id:
        try:
            with open('aflers.json','r') as file:
                prev_dict = json.load(file)
        except FileNotFoundError:
            return
        d = prev_dict.get(str(message.author.id))
        #il contatore non può ovviamente andare sotto 0
        if d[weekdays.get(datetime.today().weekday())] != 0:
            d[weekdays.get(datetime.today().weekday())] -= 1
            update_json_file(prev_dict)

@client.event
async def on_reaction_add(reaction, user):
    """Controlla se chi reagisce ai messaggi ha i requisiti per farlo"""
    if reaction.message.channel.id == REACTION_CHECK_CHANNEL_ID:
        if client.get_guild(GUILD_ID).get_role(ACTIVE_ROLE_ID) not in user.roles:
            await reaction.remove(user)

@client.event
async def on_message_edit(before, after):
    """"Controlla che i messaggi non vengano editati per inserire parole della lista banned_words"""
    if (contains_banned_words(after)):
        await after.delete()

@client.event
async def on_member_join(member):
    """Invia il messaggio di benvenuto al membro che si è appena unito al server"""
    print('nuovo membro')
    channel = await member.create_dm()
    await channel.send(greetings)

@tasks.loop(minutes=1)
async def periodic_checks():
    """Task periodica per la gestione di:
           - assegnamento ruolo attivo
           - rimozione ruolo attivo
           - (TODO)rimozione strike/violazioni

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
            guild = client.get_guild(GUILD_ID)
            await guild.get_member(int(key)).add_roles(guild.get_role(ACTIVE_ROLE_ID))
            print('member ' + key + ' is active')
            channel = client.get_channel(MAIN_CHANNEL)
            await channel.send('membro ' + key + ' è diventato attivo')

        #rimuovo i messaggi contati 7 giorni fa
        item[weekdays.get(datetime.today().weekday())] = 0

        #pausa artificiale per controllare se il ruolo è assegnato durante i test
        print('aspetta 15 sec...')
        await asyncio.sleep(15)
        print('passati')

        if item["active"] is True:
            expiration = datetime.date(datetime.strptime(item["expiration"], '%Y-%m-%d'))
            channel = client.get_channel(MAIN_CHANNEL)
            check = (datetime.date(datetime.now()) + timedelta(days=ACTIVE_DURATION))
            await channel.send('expire = ' + expiration.__str__() + ' check = ' + check.__str__())
            if expiration.__eq__((datetime.date(datetime.now()) + timedelta(days=ACTIVE_DURATION))): #prova per vedere se va
                guild = client.get_guild(GUILD_ID)
                await guild.get_member(int(key)).remove_roles(guild.get_role(ACTIVE_ROLE_ID))
                await channel.send('membro ' + key + ' non più attivo :(')
                item["active"] = False
                item["expiration"] = None
    update_json_file(prev_dict)

def update_counter(message):
    """Aggiorna il contatore dell'utente che ha mandato il messaggio. Se l'utente non era presente lo aggiunge
    al json inizializzando tutti i contatori a 0"""
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
                "start_of_violation_count": None,
                "active": False,
                "expiration": None
            }
            afler[weekdays.get(datetime.today().weekday())] = 1
            prev_dict[message.author.id] = afler
            #se una nuova persona viene aggiunta al json salvo l'id
            tracked_people_id.append(message.author.id)
        update_json_file(prev_dict)

def does_it_count(message):
    """Controlla se il messaggio ricevuto rispetta le condizioni per essere conteggiato ai fini del ruolo attivo"""
    if message.guild.id == GUILD_ID:
        if message.channel.id in active_channels_id:
            print('counts')
            return True
    print('doesn\'t count')
    return False

def update_json_file(data):
    """Scrive su file le modifiche apportate all' archivio json con il conteggio dei messaggi"""
    with open('aflers.json', 'w') as file:
        json.dump(data, file, indent=4)

def count_messages(item):
    """Ritorna il conteggio totale dei messaggi dei 7 giorni precedenti"""
    count = 0
    for i in weekdays:
        count += item[weekdays.get(i)]
    return count

def contains_banned_words(message):
    """Implementa il controllo sulle parole bannate"""
    if message.content.lower() in banned_words:
        return True
    return False

client.run(TOKEN)
