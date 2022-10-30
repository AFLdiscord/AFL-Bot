"""Questo modulo contiene tutti i listener per i diversi eventi rilevanti per il bot raccolti
nella classe EventCog

Contiene anche due comandi:
- updatestatus  per aggiornare l'attività del bot (sta giocando a...)
- presentation  per consentire ai nuovi membri di presentarsi

Sono inoltre presenti delle funzioni usiliarie alle funzioni del bot:
Logging
- evaluate_diff       trova le differenze tra un messaggio di discord e la sua modifica
Proposte
- add_proposal        aggiunge una nuova proposta al file che le traccia
- remove_proposal     rimuove la proposta dal file
- adjust_vote_count   aggiorna i contatori relativi a una proposta
- calculate_threshold logica per stabilire la sogli affinchè una proposta passi
"""

import re
import json
from enum import Enum
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any, Dict, List, Sequence, Union

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
        self.bot.version: str = 'v2.0'
        self.archive: Archive = Archive.get_instance()
        self.logger: BotLogger = BotLogger.get_instance()
        self.config: Config = Config.get_config()
        """guild deve essere assegnato sia qui che in on_ready:
        - all'avvio del bot, questo assegnamento restituisce None e
          l'assegnamento effettivo è lasciato a on_ready;
        - dopo ogni reload viene chiamato solo l'init, che però ora può
          assegnare la guild con successo.
        """
        self.guild: Union[discord.Guild, None] = self.bot.get_guild(self.config.guild_id)

    @commands.command(brief='aggiorna lo stato del bot')
    async def updatestatus(self, ctx: commands.Context):
        """Aggiorna lo stato del bot al contenuto di self.bot.version"""
        botstat = discord.Game(name=f'AFL {self.bot.version}')
        await self.bot.change_presence(activity=botstat)

    class Sex(Enum):
        maschio = 'maschio'
        femmina = 'femmina'
        non_binario = 'non binario'
        altro = 'altro'

        def str(self) -> str:
            return self.value

    @discord.app_commands.command(description='Usa questo comando per presentarti')
    @discord.app_commands.rename(age='età', sex='sesso')
    @discord.app_commands.describe(
        age='la tua età',
        sex='il tuo sesso'
    )
    async def presentation(self, interaction: discord.Interaction, age: discord.app_commands.Range[int, 0, 100], sex: Sex):
        """Consente ai nuovi membri di presentarsi fornendo le informazioni richieste
        Questo comando è disponibile solo come slash command.
        I parametri sono validati automaticamente, in particolare
        - età deve essere un intero positivo
        - sesso può essere solo una delle opzioni della classe Sex

        Sintassi
        /presentation 69 maschio   # età e sesso
        """
        if interaction.channel_id != self.config.presentation_channel_id:
            # si può usare solo per presentarsi
            await interaction.response.send_message('Questo comando è riservato per la presentazione dei nuovi membri', ephemeral=True)
            return
        await interaction.user.add_roles(self.guild.get_role(self.config.afl_role_id))
        msg = f'{interaction.user.mention} si è presentato con età={age} e sesso={sex.value}'
        await interaction.response.send_message(msg)
        await self.logger.log(msg)
        channel = self.bot.get_channel(self.config.welcome_channel_id)
        welcomeMessage = discord.Embed(
            title=f'Diamo il benvenuto a {discord.utils.escape_markdown(interaction.user.display_name)}!',
            colour=discord.Colour.dark_theme().value
        )
        welcomeMessage.set_thumbnail(url=interaction.user.display_avatar)
        welcomeMessage.add_field(
            name='Presentazione:', value=f'età: {age}\nsesso: {sex.value}', inline=False)
        await channel.send(embed=welcomeMessage)
        return

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
        if not shared_functions.relevant_message(message):
            return
        if message.content.lower() == 'ping':
            response = f'pong in {round(self.bot.latency * 1000)} ms'
            await message.channel.send(response)
            return
        if re.match(r'^(420|69|\s)+$', message.content.lower()):
            response = 'nice'
            await message.channel.send(response)
            return
        if message.channel.id == self.config.presentation_channel_id:
            # non deve rispondere a eventuali messaggi di moderatori nel canale, solo a nuovi membri
            for role in message.author.roles:
                if role.id in self.config.moderation_roles_id:
                    return
            # a tutti gli altri dice di presentarsi
            await message.reply('Presentati usando il comando `/presentation`')
        link = shared_functions.link_to_clean(message.content)
        if link is not None:
            await message.delete()
            await message.channel.send(f'Link da <@{message.author.id}>:\n{link}')
            return
        if message.channel.id == self.config.poll_channel_id:
            await self.logger.log(f'membro {message.author.mention} ha aggiunto una proposta')
            add_proposal(message, self.guild)
            await self.logger.log(f'proposta aggiunta al file:\n{message.content}')
            return
        # se è un comando non verifico i contatori (come per gli slash command)
        if self.is_command(message):
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
        if not shared_functions.relevant_message(message):
            return
        if message.channel.id == self.config.poll_channel_id:
            await self.logger.log(f'rimuovo proposta\n{message.content}')
            remove_proposal(message)
            return
        try:
            item = self.archive.get(message.author.id)
        except KeyError:
            await self.logger.log(f'cancellato il messaggio di un membro non più presente nel server\n{message.author.mention}: {message.content}')
            return
        else:
            counter = ''
            if self.is_command(message):
                # non devo decrementare nulla perchè i messaggi non contano
                return
            elif valid_for_orator(message):
                item.decrease_orator_counter()
                counter = f'decrementato contatore orator di {message.author.mention}'
            elif valid_for_dank(message):
                item.decrease_dank_counter()
                counter = f'decrementato contatore dank di {message.author.mention}'
            self.archive.save()
            msg = f'messaggio di {message.author.mention} cancellato in {message.channel.mention}\n    {message.content}'
        await self.logger.log(f'{msg}\n\n{counter}', media=message.attachments)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: List[discord.Message]):
        """Invocata quando si effettua una bulk delete dei messaggi. Aggiorna i contatori di tutti
        i membri i cui messaggi sono coinvolti nella bulk delete. Il comportamento per ogni singolo
        messaggio è lo stesso della on_message_delete.
        """
        for message in messages:
            # logga tutti i messaggi
            await self.on_message_delete(message)
        channel = messages[0].channel
        await self.logger.log(f'rimossi {len(messages)} messaggi da {channel.mention}')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Controlla se chi reagisce ai messaggi postati nel canale
        proposte abbia i requisiti per farlo.
        Se il riscontro è positivo viene aggiornato il file delle proposte.
        Ignora la reaction - eliminandola - se:
        - il membro non è autorizzato a votare;
        - la reaction non è valida per la proposta;
        - la reaction viene messa a un messaggio del bot.
        """
        if not payload.channel_id == self.config.poll_channel_id:
            return
        # ignora le reaction ai suoi stessi messaggi, serve per gestire gli avvisi
        message = await self.bot.get_channel(self.config.poll_channel_id).fetch_message(payload.message_id)
        if message.author == self.bot.user or payload.emoji.name not in ('🟢', '🔴'):
            await message.remove_reaction(payload.emoji, payload.member)
            return
        # aggiorna il contatore proposte, devo aggiornarlo sempre perchè altrimenti la remove rimuove
        # un voto dal conteggio quando il bot la rimuove
        await self.logger.log(f'aggiunta reazione sulla proposta\n{message.content}')
        is_good = self._check_reaction_permissions(payload)
        if not is_good:
            # devo rimuovere la reaction perchè il membro non ha i requisiti
            try:
                message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
                await message.remove_reaction(payload.emoji, payload.member)
            except discord.NotFound:
                await self.logger.log('impossibile trovare il messaggio o la reaction cercate')
            return
        other_react = {
            react for react in message.reactions
            if react.emoji != payload.emoji.name
        }
        # controlla se il membro abbia già messo un'altra reaction, e
        # nel caso la rimuove
        if len(other_react) == 1:
            reaction = other_react.pop()
            async for user in reaction.users():
                if payload.member == user:
                    await message.remove_reaction(reaction, payload.member)
                    break
        adjust_vote_count(payload, 1)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Se la reaction è nel canale proposte, aggiorna il contatore
        della proposta di conseguenza rimuovendo il voto corrispondente.
        Ignora la rimozione di reaction a un messaggio in proposte se
        tale messaggio è stato postato dal bot stesso o se la reaction
        non era valida per la votazione.
        """
        if not payload.channel_id == self.config.poll_channel_id:
            return
        # ignora le reaction non valide per il voto
        if payload.emoji.name not in ('🟢', '🔴'):
            return
        # ignora le reaction ai suoi stessi messaggi, serve per gestire gli avvisi
        message = await self.bot.get_channel(self.config.poll_channel_id).fetch_message(payload.message_id)
        if message.author == self.bot.user:
            return
        await self.logger.log(f'rimossa reazione sulla proposta\n{message.content}')
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
        assert payload.member is not None
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
            diff = evaluate_diff(before.content, after.content)
            await self.logger.log(f'messaggio di {before.author.mention} modificato in {before.channel.mention}:\n{diff}')

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
        # controlla se il nome dell'utente è valido
        if BannedWords.contains_banned_words(member.display_name):
            await self.logger.log(f'nuovo membro {member.mention} kickato per username improprio')
            await member.kick(reason="ForbiddenUsername")
            await channel.send('Il tuo username non è consentito, ritenta l\'accesso dopo averlo modificato')
        elif self.archive.contains_nick(member.display_name):
            await self.bot.get_channel(self.config.presentation_channel_id).send('Il tuo nickname attuale è già utilizzato, modificalo dalle impostazioni del server per poter essere ammesso')
        await self.bot.get_channel(self.config.presentation_channel_id).send('Benvenuto su AFL! Presentati usando il comando `/presentation`')

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
        if before.bot:
            return
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
                last_change = item.last_nick_change
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
                    await self.logger.log(discord.utils.escape_markdown(f'Nickname di {before.mention} modificato in {new_nick} (era {before.display_name})'))
                    return
                # se il nickname non va bene, ripristino il vecchio nickname valido
                old_nick = item.nick
                await after.edit(nick=old_nick)

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        """In caso di cambio di username, resetta il nickname a quello presente nel file."""
        if before.bot:
            return
        if (before.name == after.name) and (before.discriminator == after.discriminator):
            # non ci interessa, vuol dire che ha cambiato immagine
            return
        try:
            item: Afler = self.archive.get(before.id)
        except KeyError:
            await self.logger.log(discord.utils.escape_markdown(f'utente {before.mention} non trovato nell\'archivio durante on_user_update (before:{before.name} after:{after.name})'))
            return
        old_nick: str = item.escaped_nick
        member = self.guild.get_member(after.id)
        if member is None:
            await self.logger.log('errore imprevisto nel recuperare il membro durante on_user_update')
            return
        if old_nick != member.nick:
            await self.logger.log(f'ripristino nickname di {member.mention} da `{discord.utils.escape_markdown(member.display_name)}` a `{old_nick}`')
            await member.edit(nick=old_nick)

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
            return
        elif isinstance(error, commands.CheckFailure):
            if ctx.channel.guild is None:
                await ctx.send('I comandi possono essere usati solo nel server')
            else:
                await ctx.send('Non hai i permessi per usare questo comando.', delete_after=5)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send('Il bot non ha il permesso di eseguire l\'azione richiesta', delete_after=5)
        else:
            # a questo punto è solo un errore di sintassi, il comando inesistente è gestito sopra
            assert ctx.command is not None
            await ctx.send(f'Sintassi errata, controlla come usare il comando.\n```{ctx.command.help}```')
            # potrei fare la stessa cosa mettendo ctx.send_help(ctx.command.help) ma volevo un messaggio solo
        await ctx.message.delete(delay=5)
        await self.logger.log(str(error))

    @commands.Cog.listener()
    async def on_resume(self):
        """Controlla incoerenze tra l'archivio e l'elenco membri corrente, stesso controllo
        fatto dentro on_ready.
        """
        await self.logger.log('evento on_resume')
        await self.coherency_check(self.guild.members)

    @commands.Cog.listener()
    async def on_ready(self):
        """Chiamata all'avvio del bot, invia un messaggio di avviso sul canale impostato come
        main_channel_id nel file config.json.
        Si occupa anche di:
        - avviare la task periodica per il controllo dei contatori
        - impostare lo stato del bot con le informazioni di versione.
        - controllare la coerenza dell'archivio
        """
        await self.bot.tree.sync()
        _guild = self.bot.get_guild(self.config.guild_id)
        assert _guild is not None
        self.guild = _guild
        timestamp = datetime.now()
        # salva il timestamp di avvio nel bot
        self.bot.start_time: datetime = timestamp
        botstat = discord.Game(name=f'AFL {self.bot.version}')
        await self.bot.change_presence(activity=botstat)
        # inizializzazione del logger degli eventi sul canale
        await self.logger.initialize(self.bot)
        # log dell'avvio
        await self.logger.log(f'{self.bot.user} connesso a discord')
        # controllo coerenza archivio
        await self.coherency_check(self.guild.members)
        # per evitare RuntimeExceptions se il bot si disconnette per un periodo prolungato
        if not self.periodic_checks.is_running():
            if self.config.main_channel_id is not None:
                channel = self.bot.get_channel(self.config.main_channel_id)
                await channel.send(f'AFL Bot `{self.bot.version}` avviato alle {discord.utils.format_dt(timestamp, "T")}. Il prefisso è: `{self.bot.command_prefix}`')
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
        await self.logger.log('controllo proposte...')
        await self.handle_proposals()
        await self.logger.log('controllo proposte terminato')
        await self.logger.log('controllo conteggio messaggi...')
        for id in self.archive.keys():
            item = self.archive.get(id)
            item.clean()
            count = item.count_consolidated_messages()
            if count >= self.config.orator_threshold and self.guild.get_member(id).top_role.id not in self.config.moderation_roles_id:
                orator_role = self.guild.get_role(self.config.orator_role_id)
                await self.guild.get_member(id).add_roles(orator_role)
                msg = ''
                if item.orator:
                    msg = f'<@!{id}>: rinnovato ruolo {orator_role.mention}'
                else:
                    msg = f'<@!{id}> è diventato {orator_role.mention}'
                await self.logger.log(msg)
                await role_channel.send(embed=discord.Embed(description=msg))
                item.set_orator()

            # controllo delle violazioni
            violations_count = item.reset_violations()
            if violations_count > 0:
                msg = f'rimosse le {violations_count} violazioni di <@!{id}>'
                await self.logger.log(msg)
                # rimozione del ruolo sotto sorveglianza
                surveillance_role = self.guild.get_role(
                    self.config.under_surveillance_id)
                await self.guild.get_member(id).remove_roles(surveillance_role)
                await self.logger.log(f'<@!{id}> rimosso da <@!{surveillance_role.mention}')

            # rimuovo i messaggi contati 7 giorni fa
            item.forget_last_week()

            if item.is_orator_expired():
                orator_role = self.guild.get_role(self.config.orator_role_id)
                await self.guild.get_member(id).remove_roles(orator_role)
                msg = f'<@!{id}> non è più un {orator_role.mention}'
                await self.logger.log(msg)
                await role_channel.send(embed=discord.Embed(description=f'{msg} :('))
                item.remove_orator()
            if item.is_dank_expired():
                await self.remove_dank_from_afler(item, id)
        await self.logger.log('controllo conteggio messaggi terminato')
        self.archive.save()

    async def handle_proposals(self) -> None:
        """Gestisce le proposte, verificando se hanno raggiunto un termine."""
        proposal_channel = self.bot.get_channel(self.config.poll_channel_id)
        try:
            with open('proposals.json', 'r') as file:
                proposals = json.load(file)
        except FileNotFoundError:
            await self.logger.log('nessun file di proposte trovato')
            return
        report = {
            'result': '',
            'title': '',
            'description': '',
            'colour': discord.Color
        }
        to_delete = set()
        for key in proposals:
            try:
                message: discord.Message = await self.bot.get_channel(self.config.poll_channel_id).fetch_message(key)
            except discord.NotFound:
                # capita se viene cancellata dopo un riavvio o mentre è offline
                await self.logger.log('proposta già cancellata, ignoro')
                to_delete.add(key)
                continue
            proposal = proposals[key]
            if proposal['passed']:
                report['result'] = 'passata'
                report['title'] = 'Raggiunta soglia per la proposta'
                report['description'] = 'La soglia per la proposta è stata raggiunta.'
                report['colour'] = discord.Color.green()
            elif proposal['rejected']:
                report['result'] = 'bocciata'
                report['title'] = 'Proposta bocciata'
                report['description'] = 'La proposta è stata bocciata dalla maggioranza.',
                report['colour'] = discord.Color.red()
            # TODO mettere durata proposte nella config
            elif datetime.now() - datetime.fromisoformat(proposal['timestamp']) >= timedelta(days=3):
                report['result'] = 'scaduta'
                report['title'] = 'Proposta scaduta'
                report['description'] = 'La proposta non ha ricevuto abbastanza voti.'
                report['colour'] = discord.Color.gold()
            else:
                continue
            content = discord.Embed(
                title=report['title'],
                description=report['description'],
                colour=report['colour']
            )
            content.add_field(
                name='Autore',
                value=f'<@!{message.author.id}>',
                inline=False
            )
            content.add_field(
                name='Contenuto',
                value=proposal['content'],
                inline=False
            )
            await proposal_channel.send(embed=content)
            await self.logger.log(f'proposta di <@{message.author.id}> {report["result"]}:\n\n{proposal["content"]}')
            await message.delete()
            to_delete.add(key)
        for key in to_delete:
            del proposals[key]
        shared_functions.update_json_file(proposals, 'proposals.json')

    async def remove_dank_from_afler(self, afler: Afler, id: int) -> None:
        """Rimuove il ruolo cazzaro dall'afler.

        :param afler: l'istanza nell'archivio dell'afler a cui rimuovere il ruolo
        :param id: l'id di discord dell'afler
        """
        role_channel = self.bot.get_channel(self.config.main_channel_id)
        dank_role = self.guild.get_role(self.config.dank_role_id)
        await self.guild.get_member(id).remove_roles(dank_role)
        msg = f'<@!{id}> non è più un {dank_role.mention}'
        await self.logger.log(msg)
        await role_channel.send(embed=discord.Embed(description=f'{msg} :)'))
        afler.remove_dank()

    async def set_dank(self, afler: Afler, id: int) -> None:
        """Imposta il ruolo cazzaro dall'afler.

        :param afler: l'istanza nell'archivio dell'afler a cui conferire il ruolo
        :param id: l'id di discord dell'afler
        """
        role_channel = self.bot.get_channel(self.config.main_channel_id)
        dank_role = self.guild.get_role(self.config.dank_role_id)
        await self.guild.get_member(id).add_roles(dank_role)
        msg = ''
        if afler.dank:
            msg = f'<@!{id}>: rinnovato ruolo {dank_role.mention}'
        else:
            msg = f'<@!{id}> è diventato un {dank_role.mention}'
        await self.logger.log(msg)
        await role_channel.send(embed=discord.Embed(description=msg))
        afler.set_dank()

    async def coherency_check(self, members: Sequence[discord.Member]) -> None:
        """Controlla la coerenza tra l'elenco membri del server e l'elenco
        degli id salvati nell'archivio aflers.json
        Questo è per evitare incongruenze in caso di downtime del bot.

        In particolare si occupa di:
        - rimuovere membri usciti dal server
        - aggiungere membri non presenti

        :param members: l'elenco dei membri del server
        """
        archived_ids = list(self.archive.keys())
        members_ids_and_nick: Dict[int, str] = {}
        # salva tutti gli id dei membri presenti
        for member in members:
            if not member.bot:
                members_ids_and_nick[member.id] = member.display_name
                # controlla che tutti i membri presenti esistano nell'archivio
                # quelli che mancano vengono aggiunti
                try:
                    self.archive.get(member.id)
                except KeyError:
                    self.archive.add(
                        member.id, Afler.new_entry(member.display_name))
                    await self.logger.log(f'membro {member.mention} aggiunto all\'archivio')

        # controlla che tutti i membri archiviati siano ancora presenti
        # in caso contrario rimuove l'entry corrispondente dall'archivio
        for archived in archived_ids:
            if archived not in members_ids_and_nick:
                self.archive.remove(archived)
                await self.logger.log(f'membro <@{archived}> rimosso dall\'archivio')

        # salva i cambiamenti su file
        self.archive.save()

    def is_command(self, message: discord.Message) -> bool:
        """Controlla se il messaggio è un comando testuale.
        Serve per evitare di contare come messaggio inviato un comando.

        :param message: il messaggio in questione

        :returns: True se è un comando, altrimenti False
        :rtype: bool
        """
        # gestisce anche prefissi più lunghi
        if message.content.startswith(self.config.current_prefix):
            if not discord_markdown(message.content):
                return True
        return False


def evaluate_diff(before: str, after: str) -> str:
    """Confronta due stringhe e restituisce una stringa formattata
    che evidenzia le differenze tra le due.

    :param before: la stringa di partenza
    :param after: la stringa modificata

    :returns: una stringa formattata per evidenziare le modifiche
    :rtype: str
    """
    diff: SequenceMatcher = SequenceMatcher(None, before, after)
    output: list[str] = []
    for opcode, a0, a1, b0, b1 in diff.get_opcodes():
        if opcode == 'equal':
            output.append(diff.a[a0:a1])
        elif opcode == 'insert':
            output.append(f'**{diff.b[b0:b1]}**')
        elif opcode == 'delete':
            output.append(f'~~{diff.a[a0:a1]}~~')
        elif opcode == 'replace':
            output.append(f'~~{diff.a[a0:a1]}~~**{diff.b[b0:b1]}**')
        else:
            return f'Before:\n    {before}\nAfter:\n    {after}'
    return ''.join(output)


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
        'timestamp': message.created_at.date().isoformat(),
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
    return content[1] in ('@', '#', ':', 'a', 't', '3')


async def setup(bot: commands.Bot):
    """Entry point per il caricamento della cog"""
    await bot.add_cog(EventCog(bot))
