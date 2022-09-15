"""Questo modulo contiene tutti i listener per i diversi eventi rilevanti per il bot raccolti
nella classe EventCog

Sono inoltre presenti due funzioni usiliarie alle funzioni del bot:
Proposte
- add_proposal        aggiunge una nuova proposta al file che le traccia
- remove_proposal     rimuove la proposta dal file
- adjust_vote_count   aggiorna i contatori relativi a una proposta
- calculate_threshold logica per stabilire la sogli affinchè una proposta passi
"""

from collections import Counter
import re
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List

import discord
from discord.ext import commands, tasks
from utils import shared_functions
from utils.shared_functions import Afler, Archive, BannedWords, BotLogger, Config


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
    - on_raw_reaction_remove

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

    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.__version__ = 'v2.0alpha'
        self.archive: Archive = Archive.get_instance()
        self.logger: BotLogger = BotLogger.get_instance()
        self.config: Config = Config.get_config()
        self.guild = self.bot.get_guild(self.config.guild_id)

    @commands.command(brief='aggiorna lo stato del bot')
    async def updatestatus(self, ctx: commands.Context):
        """Aggiorna lo stato del bot al contenuto di self.__version__"""
        botstat = discord.Game(name=f'AFL {self.__version__}')
        await self.bot.change_presence(activity=botstat)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Azioni da eseguire ad ogni messaggio. Ignora i messaggi provenienti da:
        - il bot stesso
        - altri bot
        - canali di chat privata
        Il messaggio 'ping' ritorna l'intervallo di tempo tra un HEARTBEAT e il suo ack in ms.'
        Se il messaggio è nel canale di presentazione, ammette il membro automaticamente assegnandogli
        il ruolo AFL.
        """
        # TODO accorciare la funzione
        if message.author == self.bot.user or message.author.bot or message.guild != self.guild:
            return
        if message.content.lower() == 'ping':
            response = f'pong in {round(self.bot.latency * 1000)} ms'
            await message.channel.send(response)
            return
        if re.match('^(420|69|\s)+$', message.content.lower()):
            response = 'nice'
            await message.channel.send(response)
            return
        if message.channel.id == self.config.presentation_channel_id:
            # non deve rispondere a eventuali messaggi di moderatori nel canale, solo a nuovi membri
            for role in message.author.roles:
                if role.id in self.config.moderation_roles_id:
                    return
            # TODO centralizzare il controllo del nickname
            # controllo se il nick del nuovo membro è già utilizzato
            if self.archive.contains_nick(message.author.display_name):
                await message.channel.send('Il tuo nickname è già utilizzato da un altro membro, modificalo dalle impostazioni del server e ripresentati!')
                return
            if any(message.author.display_name == self.bot.get_user(afler).name for afler in self.archive.keys()):
                await message.channel.send('Questo nickname è l\'username di un utente, non puoi usarlo')
                return
            # per il resto il controllo della validità è ancora manuale
            await message.author.add_roles(self.guild.get_role(self.config.afl_role_id))
            await message.channel.send('Formidabile')
            channel = self.bot.get_channel(self.config.welcome_channel_id)
            welcomeMessage = discord.Embed(
                title=f'Diamo il benvenuto a {message.author.display_name}!',
                colour=discord.Colour.dark_theme().value
            )
            welcomeMessage.set_thumbnail(url=message.author.display_avatar)
            welcomeMessage.add_field(
                name='Presentazione:', value=message.content, inline=False)
            await channel.send(embed=welcomeMessage)
            return
        link = shared_functions.link_to_clean(message.content)
        if link is not None:
            await message.delete()
            await message.channel.send(f'Link da {message.author.display_name} :\n{link}')
            return
        if message.channel.id == self.config.poll_channel_id:
            await self.logger.log(f'membro {message.author.mention} ha aggiunto una proposta')
            add_proposal(message, self.guild)
            await self.logger.log(f'proposta aggiunta al file:\n{message.content}')
            return
        # se è un comando non verifico i contatori (come per gli slash command)
        if message.content[:1] == self.config.current_prefix:
            if not discord_markdown(message.content):
                return
        # TODO migliorare accesso a oggetto afler, magari spostandolo all'inizio o in un'altra funzione
        # controlla se il messaggio è valido
        if valid_for_orator(message):
            # controlla se il membro è già registrato nell'archivio, in caso contrario lo aggiunge
            if message.author.id in self.archive.keys():
                afler = self.archive.get(message.author.id)
            else:
                afler = Afler.new_entry(message.author.display_name)
                self.archive.add(message.author.id, afler)
            # incrementa il conteggio
            afler.increase_orator_counter()
            self.archive.save()
        elif valid_for_dank(message):
            if message.author.id in self.archive.keys():
                afler = self.archive.get(message.author.id)
            else:
                afler = Afler.new_entry(message.author.display_name)
                self.archive.add(message.author.id, afler)
            # incrementa il conteggio
            afler.increase_dank_counter()
            if afler.is_eligible_for_dank():
                await self.set_dank(afler, message.author.id)
            elif afler.is_dank_expired():
                await self.remove_dank_from_afler(afler, message.author.id)
            self.archive.save()

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Invocata alla cancellazione di un messaggio. Se era una proposta, questa viene rimossa.
        Se tale messaggio proveniva da un canale conteggiato occorre decrementare
        il contatore dell'utente corrispondente di uno.
        Per cancellazioni in bulk vedi on_bulk_message_delete.
        """
        if message.author == self.bot.user or message.author.bot or message.guild != self.guild:
            return
        if message.channel.id == self.config.poll_channel_id:
            await self.logger.log(f'rimuovo proposta\n{message.content}')
            remove_proposal(message)
            return
        if not valid_for_orator(message) and not valid_for_dank(message):
            return
        try:
            item = self.archive.get(message.author.id)
        except KeyError:
            return
        else:
            if valid_for_orator(message):
                item.decrease_orator_counter()
            else:
                item.decrease_dank_counter()
            await self.logger.log(f'decrementato contatore di {message.author.mention}')
            self.archive.save()
        # TODO gestire file multimediali
        await self.logger.log(f'messaggio di {message.author.mention} cancellato in {message.channel.mention}\n    {message.content}')

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: List[discord.Message]):
        """Invocata quando si effettua una bulk delete dei messaggi. Aggiorna i contatori di tutti
        i membri i cui messaggi sono coinvolti nella bulk delete. Il comportamento per ogni singolo
        messaggio è lo stesso della on_message_delete.
        """
        if messages[0].channel.id == self.config.poll_channel_id:
            # è qua solo in caso di spam sul canale proposte, improbabile visto la slowmode
            for message in messages:
                await self.logger.log(f'rimuovo proposta:\n{message.content}')
                remove_proposal(message)
            return
        if not valid_for_orator(messages[0]) and not valid_for_dank(messages[0]):
            return
        msg_counts = Counter(map(lambda msg: msg.author.id, messages))
        for id in msg_counts.keys():
            try:
                item = self.archive.get(id)
            except KeyError:
                continue
            else:
                if valid_for_orator(messages[0]):
                    item.decrease_orator_counter(amount=msg_counts[id])
                else:
                    item.decrease_dank_counter(amount=msg_counts[id])
        self.archive.save()
        channel = messages[0].channel
        # TODO salvare log messaggi (ad esempio in un file anziché come messaggi in chiaro)
        await self.logger.log(f'rimossi {len(messages)} messaggi da {channel.mention}')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Controlla se chi reagisce ai messaggi postati nel canale proposte abbia i requisiti per farlo.
        Se il riscontro è positivo viene anche aggiornato il file delle proposte.
        In caso l'utente non abbia i requisiti la reazione viene rimossa. Ignora le reaction ai messaggi postati
        dal bot stesso nel canale proposte.
        """
        if not payload.channel_id == self.config.poll_channel_id:
            return
        # ignora le reaction ai suoi stessi messaggi, serve per gestire gli avvisi
        message = await self.bot.get_channel(self.config.poll_channel_id).fetch_message(payload.message_id)
        if message.author == self.bot.user:
            await message.remove_reaction(payload.emoji, payload.member)
            return
        # aggiorna il contatore proposte, devo aggiornarlo sempre perchè altrimenti la remove rimuove
        # un voto dal conteggio quando il bot la rimuove
        await self.logger.log(f'aggiunta reazione sulla proposta\n{message.content}')
        adjust_vote_count(payload, 1)
        is_good = self._check_reaction_permissions(payload)
        if not is_good:
            # devo rimuovere la reaction perchè il membro non ha i requisiti
            try:
                message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
                await message.remove_reaction(payload.emoji, payload.member)
            except discord.NotFound:
                await self.logger.log('impossibile trovare il messaggio o la reaction cercate')
                return

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Se la reaction è nel canale proposte, aggiorna il contatore della proposta di conseguenza
        rimuovendo il voto corrispondente. Ignora la rimozione di reaction a un messaggio in
        proposte solo se tale messaggio è stato postato dal bot stesso.
        """
        if not payload.channel_id == self.config.poll_channel_id:
            return
        # ignora le reaction ai suoi stessi messaggi, serve per gestire gli avvisi
        message = await self.bot.get_channel(self.config.poll_channel_id).fetch_message(payload.message_id)
        if message.author == self.bot.user:
            return
        await self.logger.log(f'rimosssa reazione sulla proposta\n{message.content}')
        adjust_vote_count(payload, -1)

    def _check_reaction_permissions(self, payload: discord.RawReactionActionEvent) -> bool:
        """Controlla se la reazione è stata messa nel canale proposte da un membro che
        ne ha diritto, ovvero se:
        - è un moderatore
        - è in possesso del ruolo oratore
        Entrambi questi ruoli vanno definiti nella config (vedi template).

        :param payload: evento riguardo la reazione

        :returns: se ci interessa gestire questa reaction
        :rtype: bool
        """
        is_good = False
        orator = self.guild.get_role(self.config.orator_role_id)
        if payload.event_type == 'REACTION_ADD' and orator not in payload.member.roles:
            # se non è oratore, l'altra condizione è essere moderatore
            for role in payload.member.roles:
                if role.id in self.config.moderation_roles_id:
                    is_good = True
        else:
            # è oratore
            is_good = True
        return is_good

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Registra le modifiche dei messaggi nel log."""
        # prevent spurious activation (e.g. when embeds are loaded it counts as a modification when it shouldn't)
        if before.content != after.content:
            await self.logger.log(f'messaggio di {before.author.mention} modificato in {before.channel.mention}\nBefore:\n    {before.content}\nAfter:\n    {after.content}')

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Invia il messaggio di benvenuto all'utente entrato nel server e controlla che l'username
        sia adeguato. Se l'username contiene parole offensive l'utente viene kickato dal server con
        un messaggio che lo invita a modificare il proprio nome prima di unirsi nuovamente. Se il
        nickname è già utilizzato da un altro membro, invece, viene soltanto chiesto di modificarlo.
        """
        if member.bot:
            return
        await self.logger.log(f'nuovo membro: {member.mention}')
        channel = await member.create_dm()
        await channel.send(self.config.greetings)
        if BannedWords.contains_banned_words(member.display_name):
            await self.logger.log(f'nuovo membro {member.mention} kickato per username improprio')
            await member.kick(reason="ForbiddenUsername")
            await channel.send('Il tuo username non è consentito, ritenta l\'accesso dopo averlo modificato')
        elif self.archive.contains_nick(member.display_name):
            await self.bot.get_channel(self.config.presentation_channel_id).send(f'Il tuo nickname attuale è già utilizzato, modificalo dalle impostazioni del server per poter essere ammesso')

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Rimuove, se presente, l'utente da aflers.json nel momento in cui lascia il server."""
        if member.bot:
            return
        await self.logger.log(f'membro {member.mention} rimosso/uscito dal server')
        self.archive.remove(member.id)
        self.archive.save()

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Salva nell'archivio il nickname e la data del nuovo membro di AFL.
        Principalmente, controlla se il cambio di nick è valido. Il nickname non è valido
        in caso di:
        - modifica avvenuta prima del cooldown (solo per AFL)
        - parola vietata al suo interno
        - coincidenza con il nickname di un altro membro nel server
        - coincidenza con l'username di un altro membro del server
        """
        new_nick = after.display_name
        afl_role = self.guild.get_role(self.config.afl_role_id)
        dm = self.bot.get_user(before.id) if self.bot.get_user(
            before.id) is not None else self.bot.get_user(before.id).create_dm()
        if afl_role not in before.roles:
            if afl_role in after.roles:
                # appena diventato AFL, crea entry e salva nickname
                await self.logger.log(f'nuova entry nell\'archivio: {after.mention}')
                afler = Afler.new_entry(new_nick)
                self.archive.add(after.id, afler)
                self.archive.save()
            else:
                # non è ancora AFL, libero di cambiare nick secondo le altre regole
                if BannedWords.contains_banned_words(new_nick):
                    await dm.send(f'Il tuo nickname contiene parole vietate ed è stato ripristino')
                elif self.archive.contains_nick(new_nick):
                    await dm.send('Questo nickname è già in uso')
                elif any(new_nick == self.bot.get_user(afler).name for afler in self.archive.keys()):
                    await dm.send('Questo nickname è l\'username di un utente, non puoi usarlo')
                else:
                    return
                await after.edit(nick=before.display_name)
        else:
            # era già AFL, controllo se il cambiamento sia legittimo
            if before.display_name != new_nick:
                try:
                    item: Afler = self.archive.get(before.id)
                except KeyError:
                    await self.logger.log(f'{before.mention} ha cambiato nickname, ma non risulta nell\'archivio')
                    return
                # se il cambio del nickname avviene per ripristino o per moderazione, non bisogna fare nulla
                if item.nick == new_nick:
                    return
                # altrimenti procedo come `setnick`, usando come contesto il canale dm
                last_change = item.last_nick_change()
                difference = datetime.date(datetime.now()) - last_change
                if difference.days < self.config.nick_change_days:
                    renewal = last_change + \
                        timedelta(days=self.config.nick_change_days)
                    days_until_renewal = renewal - \
                        datetime.date(datetime.now())
                    await dm.send(f'Potrai cambiare nickname nuovamente tra {days_until_renewal.days} giorni')
                elif BannedWords.contains_banned_words(new_nick):
                    await dm.send('Il nickname non può contenere parole offensive')
                elif self.archive.contains_nick(new_nick):
                    await dm.send('Questo nickname è già in uso')
                elif any(before.id != afler and new_nick == self.bot.get_user(afler).name for afler in self.archive.keys()):
                    await dm.send('Questo nickname è l\'username di un utente, non puoi usarlo')
                else:
                    # aggiorno il nickname nell'archivio
                    item.nick = new_nick
                    self.archive.save()
                    await dm.send(f'Nickname cambiato con successo')
                    await self.logger.log(f'Nickname di {before.mention} modificato in `{new_nick}` (era `{before.display_name}`)')
                    return
                # se il nickname non va bene, ripristino il vecchio nickname valido
                old_nick = item.nick
                await after.edit(nick=old_nick)

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        """In caso di cambio di username, resetta il nickname a quello presente nel file."""
        if (before.name == after.name) and (before.discriminator == after.discriminator):
            # non ci interessa, vuol dire che ha cambiato immagine
            return
        try:
            item: Afler = self.archive.get(before.id)
        except KeyError:
            return
        old_nick: str = item.nick
        member = self.guild.get_member(after.id)
        if old_nick != member.nick:
            await self.logger.log(f'ripristino nickname di {member.mention} da `{member.display_name}` a `{old_nick}`')
            await member.edit(nick=old_nick)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        # Rimuove un canale dall'elenco attivi se questo viene cancellato dal server.
        # Potrebbe essere esteso in futuro anche per aggiungere automaticamente canali all'elenco
        # tramite qualche interazione.

        if channel.id in self.config.active_channels_id:
            # devo controllare se è una delete o una creazione
            if channel in channel.guild.channels:
                # è appena stato creato
                return
            else:
                # da rimuovere
                await self.logger.log(f'rimosso il canale: {channel.name} (id: {channel.id})')
                self.config.active_channels_id.remove(channel.id)
                self.config.save()

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Generica gestione errori per evitare crash del bot in caso di eccezioni nei comandi.
        Per ora si limita a avvisare che le menzioni possono dare problemi con certi prefissi e a
        loggare le chiamate di comandi senza i permessi necessari. Da espandare in futuro.
        """
        if isinstance(error, commands.CommandNotFound):
            #  non triggero l'invio dell'help su markdown (menzioni, emoji personalizzate ecc.) se il prefisso è '<'
            if discord_markdown(ctx.message.content):
                return
            await ctx.send('Comando inesistente. Ecco l\'elenco dei comandi che puoi usare.')
            await ctx.send_help()   # manda tutti i comandi, necessario se ci sono più pagine
        elif isinstance(error, commands.CheckFailure):
            await ctx.send('Non hai i permessi per usare questo comando.', delete_after=5)
            await ctx.message.delete(delay=5)
        else:
            await ctx.send(f'Sintassi errata, controlla come usare il comando.\n```{ctx.command.help}```')
            # potrei fare la stessa cosa mettendo ctx.send_help(ctx.command.help) ma volevo un messaggio solo
        await self.logger.log(str(error))

    @commands.Cog.listener()
    async def on_resume(self):
        """Controlla incoerenze tra l'archivio e l'elenco membri corrente, stesso controllo
        fatto dentro on_ready.
        """
        await self.logger.log('evento on_resume')
        coherency_check(self.archive, self.guild.members)

    @commands.Cog.listener()
    async def on_ready(self):
        """Chiamata all'avvio del bot, invia un messaggio di avviso sul canale impostato come
        main_channel_id nel file config.json.
        Si occupa anche di:
        - avviare la task periodica per il controllo dei contatori
        - impostare lo stato del bot con le informazioni di versione.
        - controllare la coerenza dell'archivio
        """
        self.guild = self.bot.get_guild(self.config.guild_id)
        timestamp = datetime.time(datetime.now())
        botstat = discord.Game(name=f'AFL {self.__version__}')
        await self.bot.change_presence(activity=botstat)
        # inizializzazione del logger degli eventi sul canale
        await self.logger.initialize(self.bot)
        # log dell'avvio
        await self.logger.log(f'{self.bot.user} connesso a discord')
        # controllo coerenza archivio
        coherency_check(self.archive, self.guild.members)
        # per evitare RuntimeExceptions se il bot si disconnette per un periodo prolungato
        if not self.periodic_checks.is_running():
            if self.config.main_channel_id is not None:
                channel = self.bot.get_channel(self.config.main_channel_id)
                await channel.send(f'AFL Bot `{self.__version__}` avviato alle `{timestamp}`. Il prefisso è: `{self.bot.command_prefix}`')
            await self.logger.log('avvio task')
            self.periodic_checks.start()
        else:
            await self.logger.log('chiamata on_ready ma la task è già avviata')

    # TODO vedere asyncio.Task per gestire automaticamente la partenza del task a mezzanotte
    @tasks.loop(hours=24)
    async def periodic_checks(self):
        """Task periodica per la gestione di:
            - controllo sulle proposte
            - consolidamento dei messaggi temporanei in counter se necessario
            - azzeramento dei messaggi conteggiati scaduti
            - assegnamento/rimozione ruoli (i mod sono esclusi)
            - rimozione strike/violazioni

        Viene avviata tramite la on_ready quando il bot ha completato la fase di setup ed è
        programmata per essere eseguita ogni 24 ore da quel momento.
        """
        # TODO accorciare la funzione
        role_channel = self.bot.get_channel(self.config.main_channel_id)
        proposal_channel = self.bot.get_channel(self.config.poll_channel_id)
        await self.logger.log('controllo proposte...')
        try:
            with open('proposals.json', 'r') as file:
                proposals = json.load(file)
        except FileNotFoundError:
            await self.logger.log('nessun file di proposte trovato')
        else:
            to_delete = []
            for key in proposals:
                proposal = proposals[key]
                if proposal['passed']:
                    to_delete.append(key)
                    await self.logger.log(f'proposta passata: {proposal["content"]}')
                    content = discord.Embed(
                        title='Raggiunta soglia per la proposta',
                        description='La soglia per la proposta è stata raggiunta, in attesa di approvazione dai mod',
                        colour=discord.Color.green()
                    )
                    content.add_field(
                        name='Contenuto',
                        value=proposal['content'],
                        inline=False
                    )
                    await proposal_channel.send(embed=content)
                elif proposal['rejected']:
                    await self.logger.log(f'proposta bocciata: {proposal["content"]}')
                    content = discord.Embed(
                        title='Proposta bocciata',
                        description='La proposta è stata bocciata dalla maggioranza',
                        colour=discord.Color.red()
                    )
                    content.add_field(
                        name='Contenuto',
                        value=proposal['content'],
                        inline=False
                    )
                    await proposal_channel.send(embed=content)
                    to_delete.append(key)
                    # TODO mettere durata proposte nella config
                elif datetime.date(datetime.now() - timedelta(days=3)).__str__() >= proposal['timestamp']:
                    await self.logger.log(f'proposta scaduta: {proposal["content"]}')
                    content = discord.Embed(
                        title='Proposta scaduta',
                        description='La proposta è scaduta senza avere voti sufficienti ad essere approvata',
                        colour=discord.Color.gold()
                    )
                    content.add_field(
                        name='Contenuto',
                        value=proposal['content'],
                        inline=False
                    )
                    await proposal_channel.send(embed=content)
                    to_delete.append(key)
            for key in to_delete:
                try:
                    message = await self.bot.get_channel(self.config.poll_channel_id).fetch_message(key)
                except discord.NotFound:
                    # capita se viene cancellata dopo un riavvio o mentre è offline
                    await self.logger.log('proposta già cancellata, ignoro')
                else:
                    await message.delete()
                del proposals[key]
            shared_functions.update_json_file(proposals, 'proposals.json')
        await self.logger.log('controllo proposte terminato')
        await self.logger.log('controllo conteggio messaggi...')
        for id in self.archive.keys():
            item = self.archive.get(id)
            item.clean()
            count = item.count_consolidated_messages()
            if count >= self.config.orator_threshold and self.guild.get_member(id).top_role.id not in self.config.moderation_roles_id:
                item.set_orator()
                await self.guild.get_member(id).add_roles(self.guild.get_role(self.config.orator_role_id))
                await self.logger.log(f'membro <@!{id}> è diventato oratore')
                await role_channel.send(f'membro <@!{id}> è diventato oratore')

            # controllo sulla data dell'ultima violazione, ed eventuale reset
            # item.reset_violations()

            # rimuovo i messaggi contati 7 giorni fa
            item.forget_last_week()

            if item.is_orator_expired():
                await self.guild.get_member(id).remove_roles(self.guild.get_role(self.config.orator_role_id))
                await self.logger.log(f'membro <@!{id}> non è più un oratore')
                await role_channel.send(f'membro <@!{id}> non è più un oratore :(')
                item.remove_orator()
            if item.is_dank_expired():
                await self.remove_dank_from_afler(item, id)
        await self.logger.log('controllo conteggio messaggi terminato')
        self.archive.save()

    async def remove_dank_from_afler(self, afler: Afler, id: int) -> None:
        """Rimuove il ruolo cazzaro dall'afler.

        :param afler: l'istanza nell'archivio dell'afler a cui rimuovere il ruolo
        :param id: l'id di discord dell'afler
        """
        role_channel = self.bot.get_channel(self.config.main_channel_id)
        dank_role = self.guild.get_role(self.config.dank_role_id)
        await self.guild.get_member(id).remove_roles(dank_role)
        await self.logger.log(f'membro <@!{id}> non è più un cazzaro')
        await role_channel.send(f'membro <@!{id}> non è più un cazzaro :)')
        afler.remove_dank()

    async def set_dank(self, afler: Afler, id: int) -> None:
        """Imposta il ruolo cazzaro dall'afler.

        :param afler: l'istanza nell'archivio dell'afler a cui conferire il ruolo
        :param id: l'id di discord dell'afler
        """
        role_channel = self.bot.get_channel(self.config.main_channel_id)
        dank_role = self.guild.get_role(self.config.dank_role_id)
        await self.guild.get_member(id).add_roles(dank_role)
        await self.logger.log(f'membro <@!{id}> è diventato un cazzaro')
        await role_channel.send(f'membro <@!{id}> è diventato un cazzaro')
        afler.set_dank()


def add_proposal(message: discord.Message, guild: discord.Guild) -> None:
    """Aggiunge la proposta al file proposals.json salvando timestamp e numero di membri attivi
    in quel momento.

    :param message: messaggio mandato nel canale proposte da aggiungere
    :param guild: il server discord
    """
    proposals: Dict[str, Dict[str, Any]] = {}
    try:
        with open('proposals.json', 'r') as file:
            proposals = json.load(file)
    except FileNotFoundError:
        print('file non trovato, lo creo ora')
        with open('proposals.json', 'w+') as file:
            proposals = {}
    # TODO rendere orator_count dipendente dal contesto nel server
    orator_count = 2  # moderatori non hanno ruolo oratore
    members = guild.members
    orator_role = guild.get_role(Config.get_config().orator_role_id)
    for member in members:
        if not member.bot:
            if orator_role in member.roles:
                orator_count += 1
    # TODO valutare di spostare l'inizializzazione di proposal altrove
    proposal = {
        'timestamp': datetime.date(message.created_at).__str__(),
        'total_voters': orator_count,
        'threshold': calculate_threshold(orator_count),
        'passed': False,
        'rejected': False,
        'yes': 0,
        'no': 0,
        'content': message.content
    }
    # save as string for coherency with the loading
    proposals[str(message.id)] = proposal
    shared_functions.update_json_file(proposals, 'proposals.json')


def remove_proposal(message: discord.Message) -> None:
    """Rimuove la proposta con id uguale al messaggio passato dal file. Se non trovata
    non fa nulla.

    :param message: messaggio della proposta
    """
    try:
        with open('proposals.json', 'r') as file:
            proposals: Dict[str, Dict[str, Any]] = json.load(file)
    except FileNotFoundError:
        print('errore nel file delle proposte')
        return
    try:
        del proposals[str(message.id)]
    except KeyError:
        print('proposta non trovata')
    else:
        shared_functions.update_json_file(proposals, 'proposals.json')


def valid_for_orator(message: discord.Message) -> bool:
    """Verifica se il canale in cui è stato inviato il messaggio contribuisce
    al ruolo oratore.

    :param message: il messaggio inviato

    :returns: True se il messaggio conta, False altrimenti
    :rtype: bool
    """
    return message.channel.category_id == Config.get_config().orator_category_id


def valid_for_dank(message: discord.Message) -> bool:
    """Verifica se il canale in cui è stato inviato il messaggio contribuisce
    al ruolo cazzaro.

    :param message: il messaggio inviato

    :returns: True se il messaggio conta, False altrimenti
    :rtype: bool
    """
    return message.channel.category_id == Config.get_config().dank_category_id


def adjust_vote_count(payload: discord.RawReactionActionEvent, change: int) -> None:
    """Aggiusta il contatore dei voti in base al parametro passato. Stabilisce in autonomia
    se il voto è a favore o contrario guardando il tipo di emoji cambiata.

    :param payload: l'evento di rimozione dell'emoji
    :param change: variazione del voto (+1 o -1)
    """
    try:
        with open('proposals.json', 'r') as file:
            proposals: Dict[str, Dict[str, Any]] = json.load(file)
    except FileNotFoundError:
        print('errore nel file delle proposte')
        return
    try:
        proposal = proposals[str(payload.message_id)]
    except KeyError:
        print('impossibile trovare la proposta')
        return
    if payload.emoji.name == '🟢':
        proposal['yes'] += change
        if proposal['yes'] < 0:
            proposal['yes'] = 0
        if proposal['yes'] >= proposal['threshold']:
            proposal['passed'] = True
        else:
            # è possibile cambiare idea, il controllo lo fa la task
            proposal['passed'] = False
    else:
        # se payload.emoji.name == '🔴'
        proposal['no'] += change
        if proposal['no'] < 0:
            proposal['no'] = 0
        if proposal['no'] >= proposal['threshold']:
            proposal['rejected'] = True
        else:
            proposal['rejected'] = False
    shared_functions.update_json_file(proposals, 'proposals.json')


def calculate_threshold(orator_count: int) -> int:
    """Calcola la soglia di voti a favore necessari al passaggio di una proposta.
    Per ora il criterio è maggioranza assoluta.

    :param orator_count: totale aventi diritto al voto

    :returns: soglia affinchè la proposta passi
    :rtype: int
    """
    return int(orator_count / 2) + 1


def discord_markdown(content: str) -> bool:
    """Controlla se la stringa riconosciuta come comando è in realtà un markdown.
    Serve solo a gestire i conflitti in caso il prefisso del bot sia settato a '<'.

    I markdown di discord sono raggruppabili nelle seguenti categorie:
    <@id> -> menzione membri o ruoli
    <#id> -> menzione canali
    <:id> -> emoji personalizzate
    <a:id> -> emoji animate
    <t:timestamp> -> timestamp
    Inoltre, viene gestita l'emoticon '<3', che non viene convertita automaticamente
    nell'emoji standard quando il messaggio è inviato dal client mobile.

    :param content: comando che ha dato errore

    :returns: se rappresenta un markdown
    :rtype: bool
    """
    prefix = ['@', '#', ':', 'a', 't', '3']
    return content[1] in prefix


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


async def setup(bot: commands.Bot):
    """Entry point per il caricamento della cog"""
    await bot.add_cog(EventCog(bot))
