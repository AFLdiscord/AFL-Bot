# bot.py
import os
import json

import discord
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
MAIN_CHANNEL = int(os.getenv('MAIN_CHANNEL'))
banned_words = ['porco dio']  #todo caricare da file la lista delle parole bannate all'avvio

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    timestamp = datetime.time(datetime.now())
    print(f'{client.user} has connected to Discord! 'f'{timestamp}')
    if(MAIN_CHANNEL is not None):
        channel = client.get_channel(MAIN_CHANNEL)
        await channel.send('Bot avviato alle 'f'{timestamp}')

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

    update_counter(message)


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
    if  not does_it_count(message):
        return
    try:
        with open('aflers.json','r') as file:
            prev_list = json.load(file)
    except FileNotFoundError:
        print('file non trovato, lo creo ora')
        with open('aflers.json','w+') as file:
            prev_list = []
    finally:
        for d in prev_list:
            if message.author.id == d["ID"]:
                print('già in lista, aggiorno contatore')
                #stampa prima e dopo solo per praticità, da rimuovere dopo il testing
                print(d["text_count"])
                d["text_count"] += 1
                print(d["text_count"])
                update_json_file(prev_list)
                return  
        print('nuovo utente, creo nuova entry')      
        afler = {
            "ID": message.author.id,
            "text_count": 1,
            "violations_count": 0
        }
        prev_list.append(afler)
        update_json_file(prev_list)

def does_it_count(message):
    return True   #to do, contare solo i messaggi del server AFL sui canali specificati nel regolamento

def update_json_file(data):
    with open('aflers.json', 'w') as file:
        json.dump(data, file, indent=4)

client.run(TOKEN)
