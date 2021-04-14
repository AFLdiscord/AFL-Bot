"""Questo modulo contiene tutti i listener per i diversi eventi rilevanti per il bot raccolti
nella classe EventCog

Sono inoltre presenti due funzioni usiliarie alle funzioni del bot:
- update_counter   aggiorna il contatore dell'utente passato e aggiunge al file
- does_it_count    determina se il canale in cui è stato mandato il messaggio è conteggiato o meno
"""

import json
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks
from cogs import shared_functions
from cogs.shared_functions import BannedWords, Config

class EventCog(commands.Cog):
    """Gli eventi gestiti sono elencati qua sotto, raggruppati per categoria
    (nomi eventi autoesplicativi).
    Messaggi:
    - on_message
    - on_message_delete
    - on_bulk_message_delete
    - on_message_edit

    Reazioni:
    - on_raw_reaction_add

    Membri:
    - on_member_join
    - on_member_remove
    - on_member_update
    - on_user_update

    Gestione bot:
    - on_command_error
    - on_ready
    """

    def __init__(self, bot):
        self.bot = bot
        self.__version__ = 'v0.5'

    @commands.Cog.listener()
    async def on_message(self, message):
        """Azioni da eseguire ad ogni messaggio. Ignora i messaggi provenienti da:
        - il bot stesso
        - altri bot
        - canali di chat privata
        Il messaggio 'ping' ritorna l'intervallo di tempo tra un HEARTBEAT e il suo ack in ms.'
        Invoca la funzione update_counter per aggiornare il conteggio.
        """
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
        if message.channel.id == Config.config['poll_channel_id']:
            guild = self.bot.get_guild(Config.config['guild_id'])
            add_proposal(message, guild)
        update_counter(message)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Invocata alla cancellazione di un messaggio. Se era una proposta, questa viene rimossa.
        Se tale messaggio proveniva da un canale conteggiato occorre decrementare
        il contatore dell'utente corrispondente di uno.
        Per cancellazioni in bulk vedi on_bulk_message_delete.
        """
        if message.author == self.bot.user or message.author.bot or message.guild is None:
            return
        if message.channel.id == Config.config['poll_channel_id']:
            print('rimuovo proposta')
            remove_proposal(message)
            return
        if not does_it_count(message):
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
        if item is None:
            return
        #il contatore non può ovviamente andare sotto 0
        if item["counter"] != 0:
            item["counter"] -= 1
            shared_functions.update_json_file(prev_dict, 'aflers.json')
            print('rimosso un messaggio')

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        """Invocata quando si effettua una bulk delete dei messaggi. Aggiorna i contatori di tutti
        i membri i cui messaggi sono coinvolti nella bulk delete. Il comportamento per ogni singolo
        messaggio è lo stesso della on_message_delete.
        """
        if messages[0].channel.id == Config.config['poll_channel_id']:
            #è qua solo in caso di spam sul canale proposte, improbabile visto la slowmode
            for message in messages:
                remove_proposal(message)
            return
        if not does_it_count(messages[0]):
            return
        try:
            with open('aflers.json','r') as file:
                prev_dict = json.load(file)
        except FileNotFoundError:
            return
        counter = 0
        for message in messages:
            item = None
            try:
                item = prev_dict[str(message.author.id)]
            except KeyError:
                print('utente non presente')
                continue
            finally:
                if item is None:
                    continue
            #il contatore non può ovviamente andare sotto 0
            if item["counter"] != 0:
                item["counter"] -= 1
                counter += 1
        shared_functions.update_json_file(prev_dict, 'aflers.json')
        print('rimossi ' + str(counter) + ' messaggi')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Controlla se chi reagisce ai messaggi postati nel canale proposte abbia i requisiti per farlo.
        Se il riscontro è positivO viene anche aggiornato il file delle proposte.
        In caso l'utente non abbia i requisiti la reazione viene rimossa. Ignora le reaction ai messaggi postati
        dal bot stesso nel canale proposte.
        """
        if not payload.channel_id == Config.config['poll_channel_id']:
            return
        #ignora le reaction ai suoi stessi messaggi, serve per gestire gli avvisi
        message = await self.bot.get_channel(Config.config['poll_channel_id']).fetch_message(payload.message_id)
        if message.author == self.bot.user:
            await message.remove_reaction(payload.emoji, payload.member)
            return
        #aggiorna il contatore proposte, devo aggiornarlo sempre perchè altrimenti la remove rimuove
        #un voto dal conteggio quando il bot la rimuove
        adjust_vote_count(payload, 1)
        is_good = self._check_reaction_permissions(payload)
        if not is_good:
            #devo rimuovere la reaction perchè il membro non ha i requisiti
            try:
                message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
                await message.remove_reaction(payload.emoji, payload.member)
            except discord.NotFound:
                print('impossibile trovare il messaggio o la reaction cercate')
                return

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Se la reaction è nel canale proposte, aggiorna il contatore della proposta di conseguenza
        rimuovendo il voto corrispondente. Ignora la rimozione di reaction a un messaggio in
        proposte solo se tale messaggio è stato postato dal bot stesso.
        """
        if not payload.channel_id == Config.config['poll_channel_id']:
            return
        #ignora le reaction ai suoi stessi messaggi, serve per gestire gli avvisi
        message = await self.bot.get_channel(Config.config['poll_channel_id']).fetch_message(payload.message_id)
        if message.author == self.bot.user:
            return
        adjust_vote_count(payload, -1)

    def _check_reaction_permissions(self, payload: discord.RawReactionActionEvent) -> bool:
        """Controlla se la reazione è stata messa nel canale proposte da un membro che
        ne ha diritto, ovvero se:
        - è un moderatore
        - è in possesso del ruolo attivo
        Entrambi questi ruoli vanno definiti nella config (vedi template).

        :param payload: evento riguardo la reazione

        :returns: se ci interessa gestire questa reaction
        :rtype: bool
        """
        is_good = False
        active = self.bot.get_guild(Config.config['guild_id']).get_role(Config.config['active_role_id'])
        if payload.event_type == 'REACTION_ADD' and active not in payload.member.roles:
            #se non è attivo, l'altra condizione è essere moderatore
            for role in payload.member.roles:
                if role.id in Config.config['moderation_roles_id']:
                    is_good = True
        else:
            #è attivo
            is_good = True
        return is_good

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Controlla che i messaggi non vengano editati per inserire parole della lista banned_words.
        Se viene trovata una parola bannata dopo l'edit il messaggio viene cancellato.
        """
        if BannedWords.contains_banned_words(after.content):
            await after.delete()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Invia il messaggio di benvenuto all'utente entrato nel server e controlla che l'username
        sia adeguato. Se l'username contiene parole offensive l'utente viene kickato dal server con
        un messaggio che lo invita a modificare il proprio nome prima di unirsi nuovamente.
        """
        if member.bot:
            return
        print('nuovo membro')
        channel = await member.create_dm()
        await channel.send(Config.config['greetings'])
        if BannedWords.contains_banned_words(member.display_name):
            await member.kick(reason="ForbiddenUsername")
            await channel.send('Il tuo username non è consentito, ritenta l\'accesso dopo averlo modificato')

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Rimuove, se presente, l'utente da aflers.json nel momento in cui lascia il server."""
        if member.bot:
            return
        with open('aflers.json','r') as file:
            prev_dict = json.load(file)
            try:
                del prev_dict[str(member.id)]
            except KeyError:
                print('utente non trovato')
                return
        shared_functions.update_json_file(prev_dict, 'aflers.json')

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Impedisce ai membri del server di modificare il proprio username includendo parole offensive.
        Se possibile ripristina il nickname precedente, altrimenti il membro viene kickato dal server con
        un messaggio che lo invita a modificare il proprio nome prima di unirsi nuovamente.
        """
        guild = self.bot.get_guild(Config.config['guild_id'])
        member = guild.get_member(after.id)
        if BannedWords.contains_banned_words(after.display_name):
            if before.nick is not None:
                print('ripristino nickname a ' + str(after.id))
                await member.edit(nick=before.display_name)
            else:
                channel = await member.create_dm()
                await member.kick(reason="ForbiddenNickname")
                await channel.send('Il tuo nickname non è consentito, quando rientri impostane uno valido')

    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        """Controlla che gli utenti non cambino nome mostrato qualora cambiassero username.
        In pratica, se un membro non ha impostato un nickname personalizzato per il server
        il nome mostrato cambia in base all'username anche se il membro non ha i permessi per cambiare
        nickname. Quando l'username viene modificato e il nome mostrato (display_name) cambia
        questo viene ripristinato al valore precedente.

        Problemi noti: display_name per un User ritorna sempre e comunque l'username quindi
        è possibile bypassare questo meccanismo di ripristino del nome cambiandolo due volti di fila,
        come descritto nella issue #10. In tal caso occorre intervenire manualmente.

        Per informazioni complete vedere documenti di discord.py
        """
        guild = self.bot.get_guild(Config.config['guild_id'])
        if after.display_name != before.display_name:
            print('cambio nickname')
            await guild.get_member(after.id).edit(nick=before.display_name)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Generica gestione errori per evitare crash del bot in caso di eccezioni nei comandi.
        Per ora si limita a avvisare che le menzioni possono dare problemi con certi prefissi e a
        loggare le chiamate di comandi senza i permessi necessari. Da espandare in futuro"""
        if isinstance(error, commands.CommandNotFound):
            print('comando non trovato (se hai prefisso < ogni menzione a inizio messaggio da questo errore)')
        elif isinstance(error, commands.CheckFailure):
            await ctx.send('non hai i permessi per usare questo comando', delete_after=5)
            await ctx.message.delete(delay=5)
        else:
            await ctx.send('Sintassi errata, controlla come usare il comando con "<help *nome_comando*"')
        print(error)

    @commands.Cog.listener()
    async def on_ready(self):
        """Chiamata all'avvio del bot, invia un messaggio di avviso sul canale impostato come
        MAIN_CHANNEL. Si occupa anche di avviare la task periodica per il controllo dei contatori e
        impostare lo stato del bot con le informazioni di versione."""
        timestamp = datetime.time(datetime.now())
        botstat = discord.Game(name='AFL ' + self.__version__)
        await self.bot.change_presence(activity=botstat)
        print(f'{self.bot.user} has connected to Discord! 'f'{timestamp}')
        if not self.periodic_checks.is_running():    #per evitare RuntimeExceptions se il bot si disconnette per un periodo prolungato
            if Config.config['main_channel_id'] is not None:
                channel = self.bot.get_channel(Config.config['main_channel_id'])
                await channel.send('AFL Bot `' + self.__version__ + '` avviato alle `'f'{timestamp}`. Il prefisso è: `{self.bot.command_prefix}`')
            print('avvio task')
            self.periodic_checks.start()
        else:
            print('task già avviata')

    @tasks.loop(hours=24)
    async def periodic_checks(self):
        """Task periodica per la gestione di:
            - rimozione delle proposte scadute
            - controllo sulle proposte passate con relativo avviso
            - consolidamento dei messaggi temporanei in counter se necessario
            - azzeramento dei messaggi conteggiati scaduti
            - assegnamento/rimozione ruolo attivo (i mod sono esclusi)
            - rimozione strike/violazioni

        Viene avviata tramite la on_ready quando il bot ha completato la fase di setup ed è
        programmata per essere eseguita ogni 24 ore da quel momento.
        """
        print('controllo proposte')
        try:
            with open('proposals.json','r') as file:
                proposals = json.load(file)
        except FileNotFoundError:
            print('nessun file di proposte trovato')
        else:
            to_delete = []
            for key in proposals:
                proposal = proposals[key]
                if proposal['passed']:
                    to_delete.append(key)
                    channel = self.bot.get_channel(Config.config['poll_channel_id'])
                    await channel.send(
                        'Raggiunta soglia per la proposta, in attesa di approvazione dai mod.\n' +
                        '`' + proposal['content'] + '`'
                    )
                elif datetime.date(datetime.now() - timedelta(days=3)).__str__() == proposal['timestamp']:
                    to_delete.append(key)
            for key in to_delete:
                try:
                    message = await self.bot.get_channel(Config.config['poll_channel_id']).fetch_message(key)
                except discord.NotFound:
                    print('proposta già cancellata, ignoro')  #capita se viene cancellata dopo un riavvio o mentre è offline
                else:
                    await message.delete()
                del proposals[key]
            shared_functions.update_json_file(proposals, 'proposals.json')
        print('controllo conteggio messaggi')
        try:
            with open('aflers.json','r') as file:
                prev_dict = json.load(file)
        except FileNotFoundError:
            print('nessun file di messaggi trovato')
            return
        for key in prev_dict:
            item = prev_dict[key]
            shared_functions.clean(item)
            count = shared_functions.count_consolidated_messages(item)
            if count >= Config.config['active_threshold'] and self.bot.get_guild(Config.config['guild_id']).get_member(int(key)).top_role.id not in Config.config['moderation_roles_id']:
                item["active"] = True
                item["expiration"] = datetime.date(datetime.now() + timedelta(days=Config.config['active_duration'])).__str__()
                guild = self.bot.get_guild(Config.config['guild_id'])
                await guild.get_member(int(key)).add_roles(guild.get_role(Config.config['active_role_id']))
                print('member ' + key + ' is active')
                channel = self.bot.get_channel(Config.config['main_channel_id'])
                await channel.send('membro <@!' + key + '> è diventato attivo')
                #azzero tutti i contatori
                for i in shared_functions.weekdays:
                    item[shared_functions.weekdays.get(i)] = 0

            #controllo sulla data dell'ultima violazione, ed eventuale reset
            if item["last_violation_count"] is not None:
                expiration = datetime.date(datetime.strptime(item["last_violation_count"], '%Y-%m-%d'))
                if (expiration + timedelta(days=Config.config["violations_reset_days"])).__eq__(datetime.date(datetime.now())):
                    print('reset violazioni di ' + key)
                    item["violations_count"] = 0
                    item["last_violation_count"] = None

            #rimuovo i messaggi contati 7 giorni fa
            item[shared_functions.weekdays.get(datetime.today().weekday())] = 0

            if item["active"] is True:
                expiration = datetime.date(datetime.strptime(item["expiration"], '%Y-%m-%d'))
                channel = self.bot.get_channel(Config.config['main_channel_id'])
                if expiration.__eq__((datetime.date(datetime.now()))):
                    guild = self.bot.get_guild(Config.config['guild_id'])
                    await guild.get_member(int(key)).remove_roles(guild.get_role(Config.config['active_role_id']))
                    await channel.send('membro <@!' + key + '> non più attivo :(')
                    item["active"] = False
                    item["expiration"] = None
        shared_functions.update_json_file(prev_dict, 'aflers.json')

def add_proposal(message: discord.Message, guild: discord.Guild) -> None:
    """Aggiunge la proposta al file proposals.json salvando timestamp e numero di membri attivi
    in quel momento.

    :param message: messaggio mandato nel canale proposte da aggiungere
    :param guild: il server discord
    """
    proposals = {}
    try:
        with open('proposals.json','r') as file:
            proposals = json.load(file)
    except FileNotFoundError:
        print('file non trovato, lo creo ora')
        with open('proposals.json','w+') as file:
            proposals = {}
    active_count = 2 #moderatori non hanno ruolo attivo
    members = guild.members
    active_role = guild.get_role(Config.config['active_role_id'])
    for member in members:
        if not member.bot:
            if active_role in member.roles:
                active_count += 1
    proposal = {
        'timestamp': datetime.date(message.created_at).__str__(),
        'total_voters': active_count,
        'threshold': calculate_threshold(active_count),
        'passed': False,
        'yes': 0,
        'no': 0,
        'content': message.content
    }
    proposals[message.id] = proposal
    shared_functions.update_json_file(proposals, 'proposals.json')

def remove_proposal(message: discord.Message) -> None:
    """Rimuove la proposta con id uguale al messaggio passato dal file. Se non trovata
    non fa nulla.

    :param message: messaggio della proposta
    """
    with open('proposals.json', 'r') as file:
        proposals = json.load(file)
    try:
        del proposals[str(message.id)]
    except KeyError:
        print('proposta non trovata')
    else:
        shared_functions.update_json_file(proposals, 'proposals.json')

def update_counter(message: discord.Message) -> None:
    """Aggiorna il contatore dell'utente autore del messaggio passato. In caso l'utente non sia presente
    nel file aflers.json lo aggiunge inizializzando tutti i contatori dei giorni a 0 e counter a 1.
    Si occupa anche di aggiornare il campo "last_message_date".

    :param message: messaggio ricevuto
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
                    day = shared_functions.weekdays[datetime.date(datetime.strptime(item["last_message_date"], '%Y-%m-%d')).weekday()]
                    item[day] = item["counter"]
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
        shared_functions.update_json_file(prev_dict, 'aflers.json')

def does_it_count(message: discord.Message) -> bool:
    """Controlla se il canale in cui è stato mandato il messaggio passato rientra nei canali
    conteggiati stabiliti nel file di configurazione. Ritorna un booleano con la risposta.

    :param message: il messaggio di cui controllare il canale

    :returns: True se il messaggio conta, False altrimenti
    :rtype: bool
    """
    if message.guild is not None:
        if message.guild.id == Config.config['guild_id']:
            if message.channel.id in Config.config['active_channels_id']:
                return True
    return False

def adjust_vote_count(payload: discord.RawReactionActionEvent, change: int) -> None:
    """Aggiusta il contatore dei voti in base al parametro passato. Stabilisce in autonomia
    se il voto è a favore o contrario guardando il tipo di emoji cambiata.

    :param payload: l'evento di rimozione dell'emoji
    :param change: variazione del voto (+1 o -1)
    """
    try:
        with open('proposals.json','r') as file:
            proposals = json.load(file)
    except FileNotFoundError:
        print('errore nel file delle proposte')
        return
    try:
        proposal = proposals[str(payload.message_id)]
    except KeyError:
        print('impossibile trovare la proposta')
        return
    if str(payload.emoji.name).__eq__('\U0001F7E2'):  #sarebbe :green_circle:
        proposal['yes'] += change
        if proposal['yes'] < 0:
            proposal['yes'] = 0
        if proposal['yes'] >= proposal['threshold']:
            proposal['passed'] = True
        else:
            proposal['passed'] = False   #è possibile cambiare idea, il controllo lo fa la task
    else:
        proposal['no'] += change
        if proposal['no'] < 0:
            proposal['no'] = 0
    shared_functions.update_json_file(proposals, 'proposals.json')

def calculate_threshold(active_count: int) -> int:
    """Calcola la soglia di voti a favore necessari al passaggio di una proposta.
    Per ora il criterio è maggioranza assoluta.

    :param active_count: totale aventi diritto al voto

    :returns: soglia affinchè la proposta passi
    :rtype: int
    """
    return int(active_count / 2) + 1

def setup(bot):
    """Entry point per il caricamento della cog"""
    bot.add_cog(EventCog(bot))
