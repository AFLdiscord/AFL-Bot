import json
import discord
from discord.ext import commands
from datetime import datetime, timedelta
from cogs import sharedFunctions
from cogs.sharedFunctions import BannedWords, Config

"""contiene tutti gli eventi di interesse"""

class EventCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        """azioni da eseguire ad ogni messaggio"""
        if message.author == self.bot.user or message.author.bot or message.guild is None:
            return
        if message.content.lower() == 'ping':
            response = 'pong in ' f'{round(self.bot.latency * 1000)} ms'
            await message.channel.send(response)
            return
        if (message.content == '69' or
            message.content == '420'):
            response = 'nice'
            await message.channel.send(response)
            return
        if BannedWords.contains_banned_words(message.content) and message.channel.id not in Config.config['exceptional_channels_id']:
            #cancellazione e warn fatto nella cog ModerationCog, qua serve solo per non contare il messaggio
            return
        update_counter(self, message)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """In caso di rimozione dei messaggi va decrementato il contatore della persona che
        lo aveva scritto per evitare che messaggi non adatti vengano conteggiati nell'assegnamento del ruolo.
        Vanno considerate le cancellazioni solo dai canali conteggiati.
        """
        if message.author == self.bot.user or message.author.bot or message.guild is None:
            return
        if not does_it_count(self, message):
            return
        try:
            with open('aflers.json','r') as file:
                prev_dict = json.load(file)
        except FileNotFoundError:
            return
        item = None
        try:
            item = prev_dict[str(message.author.id)]
        except KeyError:
            print('utente non presente')
            return
        finally:
            if item is None:
                return
        #il contatore non può ovviamente andare sotto 0
        if item["counter"] != 0:
            item["counter"] -= 1
            sharedFunctions.update_json_file(prev_dict, 'aflers.json')
            print('rimosso un messaggio')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Controlla se chi reagisce ai messaggi ha i requisiti per farlo"""
        if payload.channel_id == Config.config['poll_channel_id'] and payload.event_type == 'REACTION_ADD':
            if self.bot.get_guild(Config.config['guild_id']).get_role(Config.config['active_role_id']) not in payload.member.roles:
                for role in payload.member.roles:
                    if role.id in Config.config['moderation_roles_id']:
                        return
                try:
                    message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
                    await message.remove_reaction(payload.emoji, payload.member)
                except discord.NotFound:
                    print('impossibile trovare il messaggio o la reaction cercate')
                    return

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """"Controlla che i messaggi non vengano editati per inserire parole della lista banned_words"""
        if (BannedWords.contains_banned_words(after.content)):
            await after.delete()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Invia il messaggio di benvenuto al membro che si è appena unito al server e controlla che l'username
        sia adeguato
        """
        if member.bot:
            return
        print('nuovo membro')
        channel = await member.create_dm()
        await channel.send(Config.config['greetings'])
        if BannedWords.contains_banned_words(member.display_name):
            await member.kick(reason="ForbiddenUsername")
            await channel.send(f'Il tuo username non è consentito, ritenta l\'accesso dopo averlo modificato')

    @commands.Cog.listener()
    async def on_member_remove(self, member):
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

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """controlla che chi è entrato e ha modificato il nickname ne abbia messo uno adeguato"""
        guild = self.bot.get_guild(Config.config['guild_id'])
        if BannedWords.contains_banned_words(after.display_name):
            if before.nick is not None:
                print('ripristino nickname a ' + str(after.id))
                await guild.get_member(after.id).edit(nick=before.display_name)
            else:
                channel = await member.create_dm()
                await member.kick(reason="ForbiddenNickname")
                await channel.send(f'Il tuo nickname non è consentito, quando rientri impostane uno valido')

    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        """controlla che gli utenti non cambino nome mostrato qualora cambiassero username"""
        guild = self.bot.get_guild(Config.config['guild_id'])
        if after.display_name != before.display_name:
            print('cambio nickname')
            await guild.get_member(after.id).edit(nick=before.display_name)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """generica gestione errori per evitare crash banali, da espandare in futuro"""
        if isinstance(error, commands.CommandNotFound):
            print('comando non trovato (se hai prefisso < ogni menzione a inizio messaggio da questo errore)')
        elif isinstance(error, commands.CheckFailure):
            await ctx.send('non hai i permessi per usare questo comando', delete_after=5)
            await ctx.message.delete(delay=5)
        print(error)

def update_counter(cog, message):
    """aggiorna il contatore dell'utente che ha mandato il messaggio. Se l'utente non era presente lo aggiunge
    al json inizializzando tutti i contatori a 0. Si occupa anche di aggiornare il campo "last_message_date".
    """
    if not does_it_count(cog, message):
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
            item = prev_dict[key]
            if item["last_message_date"] == datetime.date(datetime.now()).__str__():   
                #messaggi dello stesso giorno, continuo a contare
                item["counter"] += 1
            elif item["last_message_date"] is None:
                #può succedere in teoria se uno riceve un warn senza aver mai scritto un messaggio (tecnicamente add_warn lo prevede)
                #oppure se resetto il file a mano per qualche motivo
                item["counter"] = 1
                item["last_message_date"] = datetime.date(datetime.now()).__str__()
            else:
                #è finito il giorno, salva i messaggi di "counter" nel giorno corrispondente e aggiorna data ultimo messaggio
                if item["counter"] != 0:
                    day = sharedFunctions.weekdays[datetime.date(datetime.strptime(item["last_message_date"], '%Y-%m-%d')).weekday()]
                    item[day] = item["counter"]   #ah ah D-day
                item["counter"] = 1
                item["last_message_date"] = datetime.date(datetime.now()).__str__()
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

def does_it_count(cog, message):
    """controlla se il messaggio ricevuto rispetta le condizioni per essere conteggiato ai fini del ruolo attivo"""
    if message.guild is not None:
        if message.guild.id == Config.config['guild_id']:
            if message.channel.id in Config.config['active_channels_id']:
                return True
    return False

def setup(bot):
    bot.add_cog(EventCog(bot))