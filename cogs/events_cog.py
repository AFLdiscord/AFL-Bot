"""Questo modulo contiene tutti i listener per i diversi eventi rilevanti per il bot raccolti
nella classe EventCog

Contiene anche due comandi:
- updatestatus  per aggiornare l'attività del bot (sta giocando a...)
- presentation  per consentire ai nuovi membri di presentarsi
"""

import re
from datetime import date, datetime, time as t, timedelta
from enum import Enum
# tzset is not available on windows
# this is not a fix, just a workaround to allow testing on windows
# since the bot will run on a linux server
try:
    from time import tzset  # Vedere periodic_checks
except ImportError:
    def tzset():
        ...

from typing import Sequence, Tuple

import discord
from discord.ext import commands, tasks
from discord.utils import escape_markdown

from aflbot import AFLBot
from utils import shared_functions as sf
from utils.afler import Afler
from utils.archive import Archive
from utils.banned_words import BannedWords
from utils.bot_logger import BotLogger
from utils.config import Config
from utils.proposals import Proposals


class EventCog(commands.Cog):
    """Gli eventi gestiti sono elencati qua sotto, raggruppati per categoria
    (nomi eventi autoesplicativi).
    Messaggi:
    - on_message
    - on_message_delete
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

    def __init__(self, bot: AFLBot):
        self.bot: AFLBot = bot
        self.bot.version = 'v2.4.5'
        self.archive: Archive = Archive.get_instance()
        self.logger: BotLogger = BotLogger.get_instance()
        self.config: Config = Config.get_config()
        self.proposals: Proposals = Proposals.get_instance()

    @commands.command(brief='aggiorna lo stato del bot')
    async def updatestatus(self, ctx: commands.Context):
        """Aggiorna lo stato del bot al contenuto di self.bot.version"""
        botstat = discord.CustomActivity(name=f'{self.bot.version}')
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
        """Consente ai nuovi membri di presentarsi fornendo le informazioni richieste.
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
        assert isinstance(interaction.user, discord.Member)
        new_member = interaction.user
        if self.config.afl_role in new_member.roles:
            await interaction.response.send_message('Ti sei già presentato, ma sei ancora qui: sei un moderatore per caso?', ephemeral=True)
            return
        # controllo del nick prima di approvare la presentazione
        await interaction.response.defer(thinking=True)
        report = self.check_new_nickname(new_member.display_name, new_member.id)
        if not report[0]:
            # nick non valido
            msg = await interaction.followup.send(
                content=f'Il tuo nick nel server {report[1]}: cambialo e riprova.',
                wait=True
            )
            await msg.delete(delay=10.0)
            await self.logger.log(escape_markdown(
                f'presentazione di {new_member.mention} ({new_member.name}) '
                f'rifiutata.\nmotivo: il suo nick ({new_member.nick}) {report[1]}'
                ))
            return
        # nick valido -> presentazione
        await interaction.user.add_roles(self.config.afl_role)
        afler = Afler.new_entry(interaction.user.display_name)
        self.archive.add(interaction.user.id, afler)
        msg = f'{interaction.user.mention} si è presentato con età={age} e sesso={sex.value}'
        await interaction.followup.send(content=msg)
        await self.logger.log(msg)
        welcomeMessage = discord.Embed(
            title=f'Diamo il benvenuto a {discord.utils.escape_markdown(interaction.user.display_name)}!',
            colour=discord.Colour.dark_theme().value
        )
        welcomeMessage.set_thumbnail(url=interaction.user.display_avatar)
        welcomeMessage.add_field(
            name='Presentazione:', value=f'età: {age}\nsesso: {sex.value}', inline=False)
        await self.config.welcome_channel.send(embed=welcomeMessage)
        return

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Azioni da eseguire ad ogni messaggio. Ignora i messaggi provenienti da:
        - il bot stesso
        - altri bot
        - canali di chat privata
        Il messaggio 'ping' ritorna l'intervallo di tempo tra un HEARTBEAT e il suo ack in ms.
        Se il messaggio è nel canale di presentazione, ammette il membro automaticamente assegnandogli
        il ruolo AFL.
        Per la parte di moderazione, vedere 'moderation_cog.py'.
        """
        if not sf.relevant_message(message):
            return
        assert isinstance(message.author, discord.Member)
        # Risposte dirette
        if message.content.lower() == 'ping':
            response = f'pong in {round(self.bot.latency * 1000)} ms'
            await message.channel.send(response)
            return
        if re.match(r'^(420|69|\s)+$', message.content.lower()):
            response = 'nice'
            await message.channel.send(response)
            return
        # Gestione delle presentazioni
        if message.channel == self.config.presentation_channel:
            # non deve rispondere a eventuali messaggi di moderatori nel canale, solo a nuovi membri
            if any(x in self.config.moderation_roles for x in message.author.roles):
                return
            # a tutti gli altri dice di presentarsi
            reply = await message.reply('Presentati usando il comando `/presentation`')
            await message.delete(delay=2)
            await reply.delete(delay=3)
            return
        # Gestione delle proposte
        if message.channel == self.config.poll_channel:
            await self.proposals.add_proposal(message)
            return
        # Ignoro i comandi
        if self.is_command(message):
            return
        # Eventuale incremento dei contatori
        await self.increase_counter(message)
        # Gestione dei link
        cleaned_message = sf.clean_links(message.content)
        if cleaned_message != message.content:
            # Il contributo va considerato anche qui per ovviare all'eventuale eliminazione
            await self.increase_counter(message)
            # Se ci sono allegati, vanno riportati
            if len(message.attachments) > 0:
                attachments = []
                for a in message.attachments:
                    try:
                        attachments.append(await a.to_file(spoiler=a.is_spoiler()))
                    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                        # Skippa eventuali file non più raggiungibili, rip
                        pass
                await message.channel.send(
                        f'Da {message.author.mention}:\n{cleaned_message}',
                        files=attachments
                )
            else:
                await message.channel.send(f'Da {message.author.mention}:\n{cleaned_message}')
            # Messaggio eliminato solo alla fine per scaricare eventuali allegati correttamente
            await message.delete()

    async def increase_counter(self, message: discord.Message) -> None:
        """Controlla la categoria del canale in cui è stato mandato il
        messaggio ed incrementa il contatore corretto di conseguenza.

        :param message: il messaggio mandato
        """
        # Gestione contatori per i ruoli oratore e cazzaro
        if self.valid_for_orator(message):
            # incrementa il conteggio
            afler = self.archive.get(message.author.id)
            afler.increase_orator_buffer()
            self.archive.save()
        elif self.valid_for_dank(message):
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
        Per cancellazioni in bulk vedi il comando delete nel cog di moderazione.
        """
        if not isinstance(
                message.channel, (discord.abc.GuildChannel, discord.Thread)):
            return
        if message.channel == self.config.poll_channel:
            if message.author.bot and message.embeds[0].color == discord.Color.orange():
                await self.proposals.remove_proposal(message.id)
            return
        if not sf.relevant_message(message):
            return
        try:
            item = self.archive.get(message.author.id)
        except KeyError:
            await self.logger.log(f'cancellato il messaggio di un membro non più presente nel server\n{message.author.mention}: {message.content}')
            return
        else:
            counter = ''
            if self.is_command(message):
                # non devo decrementare nulla perchè i comandi non contano
                return
            elif self.valid_for_orator(message):
                item.decrease_orator_buffer()
                counter = f'decrementato contatore orator di {message.author.mention}'
            elif self.valid_for_dank(message):
                item.decrease_dank_counter()
                counter = f'decrementato contatore dank di {message.author.mention}'
            self.archive.save()
            msg = f'messaggio di {message.author.mention} cancellato in {message.channel.mention}\n    {message.content}'
        await self.logger.log(f'{msg}\n\n{counter}', media=message.attachments)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Registra le modifiche dei messaggi nel log."""
        if not sf.relevant_message(before):
            return
        assert isinstance(
            before.channel, (discord.abc.GuildChannel, discord.Thread))
        # va esplicitato il controllo affinché si considerino solamente
        # le modifiche effettive (ad esempio non l'aggiunta di un embed
        # che essendo vista come una modifica triggererebbe il metodo)
        if before.content != after.content:
            diff = sf.evaluate_diff(before.content, after.content)
            await self.logger.log(f'messaggio di {before.author.mention} modificato in {before.channel.mention}:\n{diff}')

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Invia il messaggio di benvenuto all'utente entrato nel server."""
        if member.bot:
            return
        if member == self.config.guild.owner:
            return
        # Ignora la cache per risolvere #68
        new_user = await self.bot.fetch_user(member.id)
        # Impone il nickname per semplificare i controlli di coerenza
        await member.edit(nick=new_user.display_name)
        # Manda il benvenuto nel canale del server
        await self.config.presentation_channel.send(
            f'Benvenuto su AFL, {member.mention}! Presentati usando il comando `/presentation`')
        await self.logger.log(f'nuovo membro: {member.mention}')

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Rimuove, se presente, l'utente da aflers.json nel momento in cui lascia il server."""
        if member.bot:
            return
        await self.logger.log(f'membro {member.mention} ({member.name}) rimosso/uscito dal server')
        self.archive.remove(member.id)
        self.archive.save()

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Aggiunge un nuovo membro di AFL all'archivio dopo aver ricevuto
        il ruolo afl.
        Controlla altrimenti se il cambio di nickname sia valido, resettandolo
        in caso di non validità del nickname o per modifica avvenuta prima
        del cooldown (solo per AFL)
        """
        if before.bot:
            return
        if before == self.config.guild.owner:
            return

        if after.nick is None:
            # Impone la presenza di un nick
            await after.edit(nick=before.display_name)
            return

        if self.config.afl_role not in before.roles:
            if (self.config.afl_role in after.roles
                and not self.archive.is_present(before.id)
            ):
                # nuovo membro AFL, aggiunto manualmente: può succedere, quando
                # qualcuno esce e rientra entro poco tempo, che un moderatore
                # lo faccia entrare skippando la presentazione.
                await self.logger.log(
                    f"nuovo membro approvato manualmente: {after.mention} "
                    f"(nick={before.nick})"
                )
                afler = Afler.new_entry(after.nick)
                self.archive.add(after.id, afler)
                self.archive.save()
            # altrimenti non è ancora diventato AFL e non va fatto nulla
            return

        # altri update che non serve gestire (per ora)
        if before.nick is None or before.nick == after.nick:
            return

        # cambio di nickname di un AFL: da gestire
        new_nick = after.nick
        # controllo la disponibilità
        report = self.check_new_nickname(new_nick, before.id)
        if not report[0]:
            # nickname non disponibile in ogni caso
            await before.send(escape_markdown(
                f'Modifica del nick in {new_nick} bloccata.\n'
                f'Motivo: {report[1]}.'
            ))
            await self.logger.log(escape_markdown(
                f'modifica del nickname di {before.mention} '
                f'({before.nick} -> {new_nick}) bloccata.\n'
                f'motivo: {report[1]}'
            ))
            await after.edit(nick=before.nick)
            return
        try:
            afler: Afler = self.archive.get(before.id)
        except KeyError:
            await self.logger.log(escape_markdown(f'membro {before.mention} ha cambiato nickname, ma non risulta nell\'archivio (before:{before.nick} after:{after.nick})'))
            return
        if after.nick == afler.nick:
            # consenti il cambio forzato del nick da parte dei moderatori
            # o per ripristino che non necessita alcun aggiornamento dell'archivio
            return
        # controllo il tempo passato dall'ultimo cambio
        if afler.can_renew_nick():
            # aggiorno il nickname nell'archivio
            afler.nick = new_nick
            self.archive.save()
            await self.logger.log(escape_markdown(
                f'modifica del nickname di {before.mention} '
                f'({before.nick} -> {new_nick}) approvata.'
            ))
        else:
            # avvisa membro quando potrà cambiare nick
            renewal = datetime.combine(afler.last_nick_change, t(0, 0))
            renewal = sf.next_datetime(renewal, self.config.nick_change_days)
            renewal = discord.utils.format_dt(renewal, 'D')
            await before.send(escape_markdown(
                f'Modifica del nick in {new_nick} bloccata. '
                f'Potrai cambiare nuovamente nickname su AFL il {renewal}.'
            ))
            await self.logger.log(escape_markdown(
                f'modifica del nickname di {before.mention} '
                f'({before.nick} -> {new_nick}) bloccata.\nmotivo: '
                f'prossimo rinnovo il {renewal}'
            ))
            await after.edit(nick=afler.nick)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Controlla se chi reagisce ai messaggi postati nel canale
        proposte abbia i requisiti per farlo.
        Se il riscontro è positivo viene aggiornato il file delle proposte.
        Ignora la reaction - eliminandola - se:
        - il membro non è autorizzato a votare;
        - la reaction non è valida per la proposta.
        """
        if payload.channel_id != self.config.poll_channel_id:
            return
        assert payload.member is not None
        if payload.member.bot:
            return
        message = await self.config.poll_channel.fetch_message(payload.message_id)
        if not (payload.emoji.name in ('🟢', '🔴') and self._check_reaction_permissions(payload)):
            await message.remove_reaction(payload.emoji, payload.member)
            return
        # aggiorna il contatore proposte, devo aggiornarlo sempre perchè
        # altrimenti la remove rimuove un voto dal conteggio quando il
        # bot la rimuove
        proposal = self.proposals.get_proposal(payload.message_id)
        assert proposal is not None
        author = self.config.guild.get_member(proposal.author)
        assert author is not None
        # rimuove l'eventuale voto opposto
        try:
            other_react = [
                react for react in message.reactions if react.emoji != payload.emoji.name].pop()
            await message.remove_reaction(other_react, payload.member)
            # TODO impedire a on_raw_reaction_remove di loggare la rimozione
            # della proposta quando viene rimossa per questo motivo, per
            # evitare di loggare due volte un cambio.
            await self.logger.log(f'cambiato voto alla proposta di {author.mention}:\n{proposal.content}')
        except (IndexError, discord.NotFound):
            await self.logger.log(f'aggiunto voto alla proposta di {author.mention}:\n{proposal.content}')
        self.proposals.adjust_vote_count(payload, 1)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Se la reaction è nel canale Proposte, aggiorna il contatore
        della proposta di conseguenza rimuovendo il voto corrispondente.
        Ignora la rimozione di reaction a un messaggio in proposte se la
        reaction non era valida per la votazione.
        """
        if payload.channel_id != self.config.poll_channel_id:
            return
        # ignora le reaction non valide per il voto
        if payload.emoji.name not in ('🟢', '🔴'):
            return
        proposal = self.proposals.get_proposal(payload.message_id)
        assert proposal is not None
        author = self.config.guild.get_member(proposal.author)
        assert author is not None
        self.proposals.adjust_vote_count(payload, -1)
        await self.logger.log(f'rimosso voto dalla proposta di {author.mention}:\n{proposal.content}')

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
        assert payload.member is not None
        return (payload.event_type == 'REACTION_ADD' and (
            self.config.orator_role in payload.member.roles or
            any(role in self.config.moderation_roles for role in payload.member.roles)))

    def check_new_nickname(self, new_nick: str, afler_id: int) -> Tuple[bool, str]:
        """Controlla se il nuovo nickname di un afler sia valido.
        Questo accade in caso di:
        - parola vietata al suo interno
        - coincidenza con il nickname di un altro membro nel server
        - coincidenza con l'username di un altro membro del server

        :param new_nick: il nickname che l'afler ha inserito
        :param afler_id: l'id dell'afler

        :returns: una tupla che indica se il nick nuovo è accettabile, e
        in caso contrario una stringa non vuota che ne indichi la ragione
        :rtype: Tuple[bool, str]
        """
        if BannedWords.contains_banned_words(new_nick):
            return (False, 'contiene parole offensive')
        # se il nick è già presente, controlla che non sia il suo vecchio
        # (in caso di reset)
        if any(new_nick == member.nick
               for (id, member) in self.archive.archive.items()
               if afler_id != id
        ):
            return (False, 'è già in uso')
        # stesso step ma con l'username
        if any(new_nick == afler.name
                 for afler in self.config.guild.members
                 if afler.id != afler_id
        ):
            return (False, 'è l\'username di un utente')
        return (True, '')

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Generica gestione errori per evitare crash del bot in caso di eccezioni nei comandi.
        Per ora si limita a avvisare che le menzioni possono dare problemi con certi prefissi e a
        loggare le chiamate di comandi senza i permessi necessari. Da espandare in futuro.
        """
        if isinstance(error, commands.CommandNotFound):
            #  non triggero l'invio dell'help su markdown (menzioni, emoji personalizzate ecc.) se il prefisso è '<'
            if sf.discord_tag(ctx.message.content):
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
        await self.coherency_check(self.config.guild.members)

    @commands.Cog.listener()
    async def on_ready(self):
        """Chiamata all'avvio del bot, invia un messaggio di avviso sul canale impostato come
        main_channel_id nel file config.json.
        Si occupa anche di:
        - avviare la task periodica per il controllo dei contatori
        - avviare il caricamento dei modelli nella classe Config (se dei
          parametri non dovessero essere validi spegne il bot)
        - impostare lo stato del bot con le informazioni di versione.
        - controllare la coerenza dell'archivio
        """
        self.config.set_bot(self.bot)
        try:
            self.config.load_models()
        except AssertionError as e:
            print('Errore nel caricamento dei parametri del bot:', e)
            await self.bot.close()
            exit()
        await self.bot.tree.sync()
        # salva il timestamp di avvio nel bot
        self.bot.start_time = datetime.now()
        botstat = discord.CustomActivity(name=f'{self.bot.version}')
        await self.bot.change_presence(activity=botstat)
        # inizializzazione del logger degli eventi sul canale
        await self.logger.initialize()
        # log dell'avvio
        await self.logger.log(f'{self.bot.user} connesso a discord')
        # controllo coerenza archivio
        await self.coherency_check(self.config.guild.members)
        # per evitare RuntimeExceptions se il bot si disconnette per un periodo prolungato
        if not self.periodic_checks.is_running():
            if self.config.main_channel_id is not None:
                await self.config.main_channel.send(f'AFL Bot `{self.bot.version}` avviato alle {discord.utils.format_dt(self.bot.start_time, "T")}. Il prefisso è: `{self.bot.command_prefix}`')
            await self.logger.log('avvio task')
            await self.periodic_checks()
            self.periodic_checks.start()
        else:
            await self.logger.log('chiamata on_ready ma la task è già avviata')

    @tasks.loop(time=t(0, 0, tzinfo=datetime.now().astimezone().tzinfo))
    async def periodic_checks(self):
        """Task periodica per la gestione di:
            - controllo sulle proposte
            - controllo su messaggi e violazioni
        Viene avviata tramite la on_ready quando il bot ha completato la
        fase di setup ed è programmata per essere eseguita ad ogni mezzanotte.
        """
        # Decommentare solo per effettuare dei test
        # tzset()
        next_dt = sf.next_datetime(datetime.now(), 1)
        if (self.periodic_checks.time is not None and
                self.periodic_checks.time[0].tzinfo != next_dt.tzinfo):
            await self.logger.log(
                f'rilevato cambio orario, passaggio a {next_dt.tzname()}')
            self.periodic_checks.change_interval(
                time=t(0, 0, tzinfo=next_dt.tzinfo))
            tzset()
        await self.logger.log('controllo proposte...')
        await self.proposals.handle_proposals()
        await self.logger.log('controllo proposte terminato')
        await self.logger.log('controllo conteggio messaggi e violazioni...')
        await self.archive.handle_counters()
        await self.logger.log('controllo conteggio messaggi e violazioni terminato')
        self.archive.save()

    async def remove_dank_from_afler(self, afler: Afler, id: int) -> None:
        """Rimuove il ruolo cazzaro dall'afler.

        :param afler: l'istanza nell'archivio dell'afler a cui rimuovere il ruolo
        :param id: l'id di discord dell'afler
        """
        member = self.config.guild.get_member(id)
        assert member is not None
        await member.remove_roles(self.config.dank_role)
        msg = f'{member.mention} non è più un {self.config.dank_role.mention}'
        await self.logger.log(msg)
        await self.config.main_channel.send(embed=discord.Embed(description=f'{msg} :)'))
        afler.remove_dank()

    async def set_dank(self, afler: Afler, id: int) -> None:
        """Imposta il ruolo cazzaro dall'afler.

        :param afler: l'istanza nell'archivio dell'afler a cui conferire il ruolo
        :param id: l'id di discord dell'afler
        """
        member = self.config.guild.get_member(id)
        assert member is not None
        await member.add_roles(self.config.dank_role)
        msg = ''
        if afler.dank:
            msg = f'{member.mention}: rinnovato ruolo {self.config.dank_role.mention}'
        else:
            msg = f'{member.mention} è diventato un {self.config.dank_role.mention}'
        await self.logger.log(msg)
        await self.config.main_channel.send(embed=discord.Embed(description=msg))
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
        archive_ids = set(self.archive.keys())
        current_members = set(m for m in members if not m.bot)
        ex_members = archive_ids.difference(set(m.id for m in current_members))
        new_members = set(m for m in members if m.id not in archive_ids)
        current_members = current_members.difference(new_members)
        # rimuovere i membri usciti
        for id in ex_members:
            self.archive.remove(id)
            # non posso usare member.mention perchè non è più membro
            await self.logger.log(f"membro <@{id}> rimosso dall'archivio")
        # aggiungere i nuovi membri entrati
        for member in new_members:
            if self.config.afl_role in member.roles:
                # AFL non presente nell'archivio, aggiungi
                self.archive.add(member.id, Afler.new_entry(member.display_name))
            else:
                # nuovo membro che non si è ancora presentato, re-invita a farlo
                # TODO: salvare lista nuovi membri non presentati
                await self.on_member_join(member)
        # controllo che i nickname siano gli stessi settati nell'archivio
        for member in current_members:
            afler = self.archive.get(member.id)
            if member.nick == afler.nick:
                continue
            if member == self.config.guild.owner:
                afler.nick = member.display_name
                continue
            if member.nick is None:
                await member.edit(nick=afler.nick)
                continue
            # nickname cambiato
            report = self.check_new_nickname(member.nick, member.id)
            if report[0] and afler.can_renew_nick():
                await self.logger.log(f'nickname di {member.mention} modificato in {escape_markdown(member.nick)} (era {afler.escaped_nick})')
                afler.nick = member.nick
                continue
            dm = member.dm_channel if member.dm_channel is not None else await member.create_dm()
            if not report[0]:
                # nickname non disponibile in ogni caso: invia motivo in dm
                await dm.send(f'Cambio di nickname rifiutato. Motivo: {report[1]}')
            else:
                renewal = datetime.combine(afler.last_nick_change, t(0, 0))
                renewal = sf.next_datetime(renewal, self.config.nick_change_days)
                await dm.send(f'Potrai cambiare nickname nuovamente a partire dal {discord.utils.format_dt(renewal, "D")}')
            await member.edit(nick=afler.nick)
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
            if not sf.discord_tag(message.content):
                return True
        return False

    def valid_for_orator(self, message: discord.Message) -> bool:
        """Verifica se il canale in cui è stato inviato il messaggio contribuisce
        al ruolo oratore.

        :param message: il messaggio inviato

        :returns: True se il messaggio conta, False altrimenti
        :rtype: bool
        """
        if isinstance(message.channel, (discord.abc.GuildChannel, discord.Thread)):
            if message.channel.category_id == Config.get_config().orator_category_id:
                return True
        return False

    def valid_for_dank(self, message: discord.Message) -> bool:
        """Verifica se il canale in cui è stato inviato il messaggio contribuisce
        al ruolo cazzaro.

        :param message: il messaggio inviato

        :returns: True se il messaggio conta, False altrimenti
        :rtype: bool
        """
        if isinstance(message.channel, (discord.abc.GuildChannel, discord.Thread)):
            if message.channel.category_id == Config.get_config().dank_category_id:
                return True
        return False


async def setup(bot: AFLBot):
    """Entry point per il caricamento della cog"""
    await bot.add_cog(EventCog(bot))
