# bot.py
import os
import json

import discord
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

#nota, forse è meglio metterle in un file di configurazione diverso?
MAIN_CHANNEL = int(os.getenv('MAIN_CHANNEL'))
ACTIVE_THRESHOLD = int(os.getenv('ACTIVE_THRESHOLD'))
ACTIVE_DURATION = int(os.getenv('ACTIVE_DURATION'))
ACTIVE_ROLE_ID = int(os.getenv('ACTIVE_ROLE'))

#todo caricare da file la lista delle parole bannate all'avvio
banned_words = ['porco dio']  

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
        #await channel.send('Bot avviato alle 'f'{timestamp}')

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
    
    if message.content in banned_words:
        await message.delete()
        return

    if update_counter(message):
        await message.author.add_roles(message.guild.get_role(ACTIVE_ROLE_ID))


@client.event
async def on_member_join(member):
    print('nuovo membro')
    greetings = """Benvenuto/a sul server discord AFL! \n
    Prima di iniziare a partecipare nel server presentati nel canale richiesta di afl indicando almeno
    - sesso
    - età
    Ti invitiamo a leggere attentamente il regolamento del server, reperibile sul canale regole.
    Per chiarimenti rivolgiti pure ai moderatori.
    Buona permanenza!"""
    channel = await member.create_dm()
    await channel.send(greetings)

def update_counter(message):
    active = False
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
            print('già in lista, aggiorno contatore')
            d["text_count"] += 1
            if d["text_count"] >= ACTIVE_THRESHOLD:
                #nota: non serve fare distinzione tra coloro che sono già attivi e coloro che 
                #rinnovano il ruolo perchè in entrambi i casi l'operazione da fare è la stessa
                d["text_count"] = 0
                d["active"] = True
                d["expiration"] = datetime.date(datetime.now() + timedelta(days=7)).__str__()
                active = True
            update_json_file(prev_dict)
            return active
        print('nuovo utente, creo nuova entry')
        afler = {
            "ID": message.author.id,
            "text_count": 1,
            "violations_count": 0,
            "active": False,
            "expiration": None
        }
        prev_dict[afler.get("ID")] = afler
        update_json_file(prev_dict)
        return active

def does_it_count(message):
    return True   #to do, contare solo i messaggi del server AFL sui canali specificati nel regolamento

def update_json_file(data):
    with open('aflers.json', 'w') as file:
        json.dump(data, file, indent=4)

client.run(TOKEN)
