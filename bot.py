# bot.py
import os

import discord
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
MAIN_CHANNEL = int(os.getenv('MAIN_CHANNEL'))

client = discord.Client()

@client.event
async def on_ready():
    timestamp = datetime.time(datetime.now())
    print(f'{client.user} has connected to Discord! 'f'{timestamp}')
    if(MAIN_CHANNEL is not None):
        channel = client.get_channel(MAIN_CHANNEL)
        await channel.send('Bot avviato alle 'f'{timestamp}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.lower() == 'ping':
        response = 'pong in ' f'{round(client.latency * 1000)} ms'
        await message.channel.send(response)

    if message.content == '69' or message.content == '420':
        response = 'nice'
        await message.channel.send(response)

client.run(TOKEN)
