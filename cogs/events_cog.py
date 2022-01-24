"""Questo modulo contiene tutti i listener per i diversi eventi rilevanti per il bot raccolti
nella classe EventCog

Sono inoltre presenti due funzioni usiliarie alle funzioni del bot:
Ruolo attivo
- update_counter      aggiorna il contatore dell'utente passato e aggiunge al file
- does_it_count       determina se il canale in cui è stato mandato il messaggio è conteggiato o meno
Proposte
- add_proposal        aggiunge una nuova proposta al file che le traccia
- remove_proposal     rimuove la proposta dal file
- adjust_vote_count   aggiorna i contatori relativi a una proposta
- calculate_threshold logica per stabilire la sogli affinchè una proposta passi
"""

import json
from datetime import datetime, timedelta
from typing import List

import discord
from discord.ext import commands, tasks
from utils import shared_functions
from utils.shared_functions import Afler, Archive, BannedWords, Config

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
    - on_raw_reactoin_remove

    Membri:
    - on_member_join
    - on_member_remove
    - on_member_update
    - on_user_update

    Gestione bot:
    - on_command_error
    - on_ready (avvia periodic_checks)

    Inoltre è presente un comando per aggiornare lo status del bot
    """

    def __init__(self, bot):
        self.bot = bot
        self.__version__ = 'v1.1.1'
        self.archive = Archive.get_instance()

    @commands.command(brief='aggiorna lo stato del bot')
    async def updatestatus(self, ctx):
        """Aggiorna lo stato del bot al contenuto di self.__version__"""
        botstat = discord.Game(name='AFL ' + self.__version__)
        await self.bot.change_presence(activity=botstat)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Azioni da eseguire ad ogni messaggio. Ignora i messaggi provenienti da:
        - il bot stesso
        - altri bot
        - canali di chat privata
        Il messaggio 'ping' ritorna l'intervallo di tempo tra un HEARTBEAT e il suo ack in ms.'
        Se il messaggio è nel canale di presentazione, ammette il membro automaticamente assegnandogli
        il ruolo AFL.
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
            # cancellazione e warn fatto nella cog ModerationCog, qua serve solo per non contare il messaggio
            return
        if message.channel.id == Config.config['presentation_channel_id']:
            # non deve rispondere a eventuali messaggi di moderatori nel canale, solo a nuovi membri
            for role in message.author.roles:
                if role.id in Config.config['moderation_roles_id']:
                    return
            # il controllo della validità è ancora manuale
            await message.author.add_roles(self.bot.get_guild(Config.config['guild_id']).get_role(Config.config['afl_role_id']))
            await message.channel.send('Formidabile')
            channel = self.bot.get_channel(Config.config['welcome_channel_id'])
            welcomeMessage = discord.Embed(
                title=f'Diamo il benvenuto a {message.author.display_name}!',
                colour=discord.Colour.dark_theme().value
            )
            welcomeMessage.set_thumbnail(url=message.author.avatar_url)
            welcomeMessage.add_field(name='Presentazione:', value=message.content, inline=False)
            await channel.send(embed=welcomeMessage)
            return
        link = shared_functions.link_to_clean(message.content)
        if link is not None:
            await message.delete()
            await message.channel.send('Link da ' + message.author.display_name + ':\n' + link)
            return
        if message.channel.id == Config.config['poll_channel_id']:
            guild = self.bot.get_guild(Config.config['guild_id'])
            add_proposal(message, guild)
        # controlla se il messaggio è valido
        if not does_it_count(message):
            return
        # controlla se il membro è già registrato nell'archivio, in caso contrario lo aggiunge
        if message.author.id in self.archive.keys():
            afler = self.archive.get(message.author.id)
        else:
            afler = Afler.new_entry(message.author.display_name)
            self.archive.add(message.author.id, afler)
        # incrementa il conteggio
        afler.increase_counter()
        self.archive.save()

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
            item = self.archive.get(message.author.id)
        except KeyError:
            print('utente non presente')
            return
        else:
            item.decrease_counter()
            self.archive.save()

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        """Invocata quando si effettua una bulk delete dei messaggi. Aggiorna i contatori di tutti
        i membri i cui messaggi sono coinvolti nella bulk delete. Il comportamento per ogni singolo
        messaggio è lo stesso della on_message_delete.
        """
        if messages[0].channel.id == Config.config['poll_channel_id']:
            # è qua solo in caso di spam sul canale proposte, improbabile visto la slowmode
            for message in messages:
                remove_proposal(message)
            return
        if not does_it_count(messages[0]):
            return
        counter = 0
        # TODO: possibile ottimizzazione, prima contare i messaggi per ogni utente e decrementare
        # in un colpo solo anzichè iterare su un messaggio alla volta
        for message in messages:
            try:
                item = self.archive.get(message.author.id)
            except KeyError:
                print('utente non presente')
                continue
            else:
                item.decrease_counter()
                counter += 1
        self.archive.save()
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
        # ignora le reaction ai suoi stessi messaggi, serve per gestire gli avvisi
        message = await self.bot.get_channel(Config.config['poll_channel_id']).fetch_message(payload.message_id)
        if message.author == self.bot.user:
            await message.remove_reaction(payload.emoji, payload.member)
            return
        # aggiorna il contatore proposte, devo aggiornarlo sempre perchè altrimenti la remove rimuove
        # un voto dal conteggio quando il bot la rimuove
        adjust_vote_count(payload, 1)
        is_good = self._check_reaction_permissions(payload)
        if not is_good:
            # devo rimuovere la reaction perchè il membro non ha i requisiti
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
        # ignora le reaction ai suoi stessi messaggi, serve per gestire gli avvisi
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
            # se non è attivo, l'altra condizione è essere moderatore
            for role in payload.member.roles:
                if role.id in Config.config['moderation_roles_id']:
                    is_good = True
        else:
            # è attivo
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
        self.archive.remove(member.id)
        self.archive.save()

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Impedisce ai membri del server di modificare il proprio username includendo parole
        offensive. Quando un membro riceve il ruolo AFL si occupa di creare la entry nel file
        di archivio salvando il nickname e la data. Quest'ultima serve per gestire il cambio
        di nickname periodico concesso agli AFL.
        """
        guild = self.bot.get_guild(Config.config['guild_id'])
        afl_role = guild.get_role(Config.config['afl_role_id'])
        if afl_role not in before.roles:
            if afl_role in after.roles:
                # appena diventato AFL, crea entry e salva nickname
                afler = Afler.new_entry(after.display_name)
                self.archive.add(after.id, afler)
                self.archive.save()
            else:
                # non è ancora AFL, libero di cambiare nick a patto che non contenga parole vietate
                if BannedWords.contains_banned_words(after.display_name):
                    print('nickname con parole vietate, ripristino a ' + str(after.id))
                    await after.edit(nick=before.display_name)
        else:
            # era già AFL, ripristino il nickname dal file
            if before.display_name != after.display_name:
                try:
                    old_nick = self.archive.get(after.id).nick
                except KeyError:
                    old_nick = before.display_name
                await after.edit(nick=old_nick)


    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        """In caso di cambio di username, resetta il nickname a quello presente nel file."""
        if (before.name == after.name) and (before.discriminator == after.discriminator):
            # non ci interessa, vuol dire che ha cambiato immagine
            return
        try:
            item = self.archive.get(before.id)
        except KeyError:
            return
        old_nick = item.nick
        member = self.bot.get_guild(Config.config['guild_id']).get_member(after.id)
        if old_nick != member.nick:
            print('reset nickname a ' + old_nick)
            await member.edit(nick=old_nick)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Rimuove un canale dall'elenco attivi se questo viene cancellato dal server.
        Potrebbe essere esteso in futuro anche per aggiungere automaticamente canali all'elenco
        tramite qualche interazione.
        """
        if channel.id in Config.config['active_channels_id']:
            # devo controllare se è una delete o una creazione
            if channel in channel.guild.channels:
                # è appena stato creato
                return
            else:
                # da rimuovere
                Config.config['active_channels_id'].remove(channel.id)
                shared_functions.update_json_file(Config.config, 'config.json')

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Generica gestione errori per evitare crash del bot in caso di eccezioni nei comandi.
        Per ora si limita a avvisare che le menzioni possono dare problemi con certi prefissi e a
        loggare le chiamate di comandi senza i permessi necessari. Da espandare in futuro."""
        if isinstance(error, commands.CommandNotFound):
            if not emoji_or_mention(ctx.message.content):
                # tutto ciò serve per non triggerare l'invio dell'help su menzioni, nomi di canali e emoji custom se il prefisso è '<'
                await ctx.send('Comando inesistente. Ecco l\'elenco dei comandi che puoi usare.')
                await ctx.send_help()   # manda tutti i comandi, necessario se ci sono più pagine
        elif isinstance(error, commands.CheckFailure):
            await ctx.send('Non hai i permessi per usare questo comando.', delete_after=5)
            await ctx.message.delete(delay=5)
        else:
            await ctx.send('Sintassi errata, controlla come usare il comando.\n' + '```' + ctx.command.help + '```')
            # potrei fare la stessa cosa mettendo ctx.send_help(ctx.command.help) ma volevo un messaggio solo
        print(error)

    @commands.Cog.listener()
    async def on_resume(self):
        """Controlla incoerenze tra l'archivio e l'elenco membri corrente, stesso controllo
        fatto dentro on_ready.
        """
        coherency_check(self.archive, self.bot.get_guild(Config.config['guild_id']).members)

    @commands.Cog.listener()
    async def on_ready(self):
        """Chiamata all'avvio del bot, invia un messaggio di avviso sul canale impostato come
        main_channel_id nel file config.json.
        Si occupa anche di:
        - avviare la task periodica per il controllo dei contatori
        - impostare lo stato del bot con le informazioni di versione.
        - controllare la coerenza dell'archivio
        """
        timestamp = datetime.time(datetime.now())
        botstat = discord.Game(name='AFL ' + self.__version__)
        await self.bot.change_presence(activity=botstat)
        print(f'{self.bot.user} has connected to Discord! 'f'{timestamp}')
        # controllo coerenza archivio
        coherency_check(self.archive, self.bot.get_guild(Config.config['guild_id']).members)
        if not self.periodic_checks.is_running():    # per evitare RuntimeExceptions se il bot si disconnette per un periodo prolungato
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
                    print('proposta già cancellata, ignoro')  # capita se viene cancellata dopo un riavvio o mentre è offline
                else:
                    await message.delete()
                del proposals[key]
            shared_functions.update_json_file(proposals, 'proposals.json')
        print('controllo conteggio messaggi')
        for id in self.archive.keys():
            item = self.archive.get(id)
            item.clean()
            count = item.count_consolidated_messages()
            if count >= Config.config['active_threshold'] and self.bot.get_guild(Config.config['guild_id']).get_member(id).top_role.id not in Config.config['moderation_roles_id']:
                item.set_active()
                guild = self.bot.get_guild(Config.config['guild_id'])
                await guild.get_member(id).add_roles(guild.get_role(Config.config['active_role_id']))
                print('member ' + item.nick + ' is active')
                channel = self.bot.get_channel(Config.config['main_channel_id'])
                await channel.send('membro <@!' + str(id) + '> è diventato attivo')
                
            # controllo sulla data dell'ultima violazione, ed eventuale reset
            item.reset_violations()

            # rimuovo i messaggi contati 7 giorni fa
            item.forget_last_week()

            if item.is_active_expired():
                channel = self.bot.get_channel(Config.config['main_channel_id'])
                guild = self.bot.get_guild(Config.config['guild_id'])
                await guild.get_member(id).remove_roles(guild.get_role(Config.config['active_role_id']))
                await channel.send('membro <@!' + str(id) + '> non più attivo :(')
                item.set_inactive()
        self.archive.save()

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
    active_count = 2 # moderatori non hanno ruolo attivo
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
    if str(payload.emoji.name).__eq__('\U0001F7E2'):  # sarebbe :green_circle:
        proposal['yes'] += change
        if proposal['yes'] < 0:
            proposal['yes'] = 0
        if proposal['yes'] >= proposal['threshold']:
            proposal['passed'] = True
        else:
            proposal['passed'] = False   # è possibile cambiare idea, il controllo lo fa la task
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

def emoji_or_mention(content: str) -> bool:
    """Controlla se la stringa riconosciuta come comando è in realtà un'emoji o
    una menzione a canali/membri. Serve solo a gestire i conflitti in caso il
    prefisso del bot sia settato a '<'.

    Conflitti noti:
    <@!id> -> menzione membri
    <#id> -> menzione canali
    <:id> -> emoji
    <a:id> -> emoji animate
    <t:timestamp> -> timestamps

    :param content: comando che ha dato errore

    :returns: se rappresenta una menzione o emoji
    :rtype: bool
    """
    if (content.startswith('<@') or content.startswith('<#') or
        content.startswith('<:') or content.startswith('<a:')) or content.startswith('<t:'):
        return True
    else:
        return False

def coherency_check(archive: Archive, members: List[discord.Member]) -> None:
    """Controlla la coerenza tra l'elenco membri del server e l'elenco
    degli id salvati nell'archivio aflers.json
    Questo è per evitare incongruenze in caso di downtime del bot.

    NOTA: ci interessa solo rimuovere i membri usciti, i membri entrati saranno
    aggiunti in automatico al primo messaggio.
    """
    archived_ids = list(archive.keys())
    members_ids = []
    # salva tutti gli id dei membri presenti
    for member in members:
        if not member.bot:
            members_ids.append(member.id)

    # controlla che tutti i membri archiviati siano ancora presenti
    # in caso contrario rimuove l'entry corrispondente dall'archivio
    for archived in archived_ids:
        if archived not in members_ids:
            archive.remove(archived)

    # save changes to file
    archive.save()

def setup(bot):
    """Entry point per il caricamento della cog"""
    bot.add_cog(EventCog(bot))
