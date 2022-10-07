""":class: ModerationCog contiene tutti i comandi per la moderazione."""
from typing import Union

import discord
from discord.ext import commands
from utils.shared_functions import Afler, Archive, BannedWords, BotLogger, Config


class ModerationCog(commands.Cog, name='Moderazione'):
    """Contiene i comandi relativi alla moderazione:
    - resetnick  reimposta il nickname dell'utente citato
    - warn       aggiunge un warn all'utente citato
    - unwarn     rimuove un warn all'utente citato
    - ban        banna l'utente citato
    - warncount  mostra i warn di tutti i membri
    Inoltre effettua il controllo sul contenuto dei messaggi e elimina quelli dal contenuto inadatto.
    Questi comandi possono essere usati solo da coloro che possiedono un ruolo di moderazione.
    """

    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.archive: Archive = Archive.get_instance()
        self.logger: BotLogger = BotLogger.get_instance()
        self.config: Config = Config.get_config()

    def cog_check(self, ctx: commands.Context):
        """Check sui comandi per autorizzarne l'uso solo ai moderatori."""
        return ctx.author.top_role.id in self.config.moderation_roles_id

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Elimina i messaggi inappropriati dai canali e aggiunge un
        warn all'utente.
        Ignora i messaggi da:
        - il bot stesso
        - altri bot
        - canali di chat privata
        - canali ignorati (vedi config.template)
        """
        if message.type not in (discord.MessageType.default, discord.MessageType.reply):
            # ignora i messaggi "di sistema" tipo creazione thread (vedi #59), pin, etc che sono generati
            # automaticamente ma vengono attribuiti all'utente che esegue l'azione
            return
        if (message.author == self.bot.user or
            message.author.bot or
                message.guild is None):
            return
        if not BannedWords.contains_banned_words(message.content):
            return
        if isinstance(message.channel, discord.Thread):
            channel_id = message.channel.parent_id
        else:
            channel_id = message.channel.id
        if channel_id in self.config.exceptional_channels_id:
            return
        await message.delete()
        await self.logger.log(f'aggiunto warn a {message.author.mention} per \
            linguaggio inappropriato: `{message.content}`')
        await self._add_warn(message.author, 'linguaggio inappropriato', 1)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Riesamina i messaggi dopo la modifica per evitare tentativi di
        bypass della censura delle parole bannate.
        """
        if before.content != after.content:
            await self.on_message(after)

    @commands.command(brief='reimposta il nickname dell\'utente citato')
    async def resetnick(self, ctx: commands.Context, attempted_member: Union[str, discord.Member] = None, *, name: str = None):
        """Reimposta il nickname di un membro se questo non è opportuno per il server
        e i controlli automatici non sono bastati a filtrarlo. Questo permette di mantenere
        il reset automatico per i nickname in caso di cambiamento impedendo i reset manuali.

        Sintassi:
        <resetnick @someone nuovo_nome  # resetta il nick di someone a nuovo_nome
          @someone messaggio citato
        <resetnick nuovo_nome           # si può anche citare un messaggio dell'interessato
        """
        if attempted_member is None:
            raise commands.CommandError   # il messaggio di errore adesso è centralizzato
        else:
            # recupero il membro e resetto il nick
            if ctx.message.reference is None:
                # tramite menzione nel messaggio, se presente
                if ctx.message.mentions is None:
                    raise commands.CommandError  # nessuna menzione
                member = ctx.message.mentions[0]
                if name is None:
                    raise commands.CommandError
            else:
                # tramite messaggio citato
                msg = await ctx.fetch_message(ctx.message.reference.message_id)
                member = msg.author
                if name is None:
                    name = attempted_member
                else:
                    name = f'{attempted_member} {name}'
        if member.bot:
            return
        try:
            item = self.archive.get(member.id)
        except KeyError:
            await ctx.send('Non tovato nel file :(', delete_after=5)
            return
        old_nick = item.nick
        item.nick = name
        self.archive.save()
        await member.edit(nick=name)
        await self.logger.log(f'Nickname di {member.mention} ripristinato in `{name}` (era `{old_nick}`)')
        await ctx.send(f'Nickname di {member.mention} ripristinato')

    @commands.command(brief='aggiunge un warn all\'utente citato')
    async def warn(self, ctx: commands.Context, attempted_member: Union[str, discord.Member] = None, *, reason: str = 'un moderatore ha ritenuto inopportuno il tuo comportamento'):
        """Aggiunge un warn all'utente menzionato nel messaggio. Si può menzionare in diversi modi.
        L'effetto è il seguente:
        - aggiunge un warn all'autore del messaggio a cui si risponde/utente menzionato
        - cancella il messaggio citato (se presente)
        - cancella il comando di warn

        Sintassi:
        <warn @someone         # warn all'utente menzionato 'someone'
        <warn @someone reason  # aggiunge una ragione specifica al warn, se non specificata
                               # reason='un moderatore ha ritenuto inopportuno il tuo comportamento'

        è possibile usarlo anche direttamente in risposta al messaggio oggetto del warn lasciando
        attiva la menzione (clic destro sul messaggio -> rispondi). In tal caso

          @someone messaggio citato
        <warn                          # aggiunge warn a 'someone'
          @someone messaggio citato
        <warn reason                   # aggiunge warn a 'someone' con ragione 'reason'
        """
        if attempted_member is None:   # nessun argomento passato al warn
            if ctx.message.reference is None:
                # sono in questo caso quando mando <warn da solo
                await ctx.send('Devi menzionare qualcuno o rispondere a un messaggio per poter usare questo comando', delete_after=5)
                return
            # in questo caso ho risposto a un messaggio con <warn
            msg = await ctx.fetch_message(ctx.message.reference.message_id)
            member = msg.author
            await msg.delete()
        else:   # con argomenti al warn
            if not ctx.message.mentions:   # nessuna menzione nel messaggio
                await ctx.send('Devi menzionare qualcuno o rispondere a un messaggio per poter usare questo comando', delete_after=5)
                return
            if ctx.message.reference is None:
                # ho chiamato il warn a mano <warn @somebody ragione
                member = ctx.message.mentions[0]
            else:
                # ho menzionato qualcuno, prendo come target del warn
                msg = await ctx.fetch_message(ctx.message.reference.message_id)
                member = msg.author
                await msg.delete()
                # solo se vado per reference devo sistemare la reason perchè la prima parola va in attempted_member
                if reason == 'un moderatore ha ritenuto inopportuno il tuo comportamento':
                    # ragione di una sola parola, altrimenti poi concatena tutto
                    reason = attempted_member
                else:
                    # devo inserire uno spazio altrimenti scrive tutto appicciato
                    reason = f'{attempted_member} {reason}'
        if member.bot:   # or member == ctx.author:
            return
        await self._add_warn(member, reason, 1)
        user = f'<@!{member.id}>'
        await self.logger.log(f'{member.mention} warnato. Motivo: {reason}')
        await ctx.send(f'{user} warnato. Motivo: {reason}')
        await ctx.message.delete(delay=5)

    @commands.command(brief='rimuove un warn all\'utente citato')
    async def unwarn(self, ctx: commands.Context, member: discord.Member):
        """Rimuove un warn all'utente menzionato. Se non aveva warn non fa nulla.

        Sintassi:
        <unwarn @someone      # rimuove un warn a 'someone'
        """
        if member.bot:
            return
        reason = 'buona condotta'
        await self._add_warn(member, reason, -1)
        user = f'<@!{member.id}>'
        await self.logger.log(f'rimosso warn a {member.mention}')
        await ctx.send(f'{user} rimosso un warn.')
        await ctx.message.delete(delay=5)

    @commands.command(brief='mostra i warn di tutti i membri', aliases=['warnc', 'wc'])
    async def warncount(self, ctx: commands.Context):
        """Stampa nel canale in cui viene chiamato l'elenco di tutti i warn degli utenti.
        Esempio output:
        1 warn
         - membro1
         - membro2
         - ...
        2 warn
         Nessuno
        3 warn
         - membro3

        Sintassi:
        <warncount
        alias: warnc, wc
        """
        # aggiornare se si cambia il conteggio dei warn
        warnc = {
            0: [],
            1: [],
            2: [],
            3: []
        }
        for user in self.archive.values():
            # ricalcolato a ogni richiesta, si potrebbe cacharlo se il numero di utenti cresce
            warnc[user.warn_count()].append(user.nick)
        # rimuovo gli utenti con 0 warn per non intasare il messaggio
        del warnc[0]
        response = ''
        for k in warnc.keys():
            response += f'{k} warn:\n'
            userlist = ''
            for name in warnc[k]:
                userlist += f' - {name}\n'
            if userlist == '':
                userlist = 'Nessuno\n'
            response += userlist
        await ctx.send(response)

    @commands.command(brief='banna il membro citato')
    async def ban(self, ctx: commands.Context, member: discord.Member = None, *, reason: str = 'un moderatore ha ritenuto inopportuno il tuo comportamento'):
        """Banna un membro dal server.

        Sintassi:
        <ban @someone     # banna 'someone'
        """
        if member is None:
            await ctx.send('specifica un membro da bannare', delete_after=5)
            await ctx.message.delete(delay=5)
            return
        user = f'<@!{member.id}>'
        await self.logger.log(f'{member.mention} bannato. Motivo: {reason}')
        await ctx.send(f'{user} bannato. Motivo: {reason}')
        await ctx.message.delete(delay=5)
        penalty = 'bannato dal server.'
        channel = await member.create_dm()
        await channel.send(f'Sei stato {penalty} Motivo: {reason}.')
        await member.ban(delete_message_days=0, reason=reason)

    async def _add_warn(self, member: discord.Member, reason: str, number: int):
        """Incrementa o decremente il numero di violazioni di numero e tiene traccia
        dell'ultima violazione commessa. Si occupa anche di inviare in dm la notifica
        dell'avvenuta violazione con la ragione che è stata specificata.
        """
        penalty = 'warnato.'
        if self.archive.is_present(member.id):
            item = self.archive.get(member.id)
            item.modify_warn(number)
            if number < 0:  # non deve controllare il ban se è un unwarn
                return
            if item.warn_count() == 3:
                role = self.bot.get_guild(self.config.guild_id).get_role(
                    self.config.under_surveillance_id)
                await member.add_roles(role)
                penalty = 'sottoposto a sorveglianza, il prossimo sara\' un ban.'
                channel = await member.create_dm()
                await channel.send(f'Sei stato {penalty} Motivo: {reason}.')
                await self.logger.log(f'{member.mention} aggiunto a {role.mention}')
            elif item.warn_count() >= 4:
                penalty = 'bannato dal server.'
                channel = await member.create_dm()
                await channel.send(f'Sei stato {penalty} Motivo: {reason}.')
                await member.ban(delete_message_days=0, reason=reason)
                await self.logger.log(f'{member.mention} bannato automaticamente per aver superato i 3 warn')
            else:
                channel = await member.create_dm()
                await channel.send(f'Sei stato {penalty} Motivo: {reason}.')
        else:
            # membro che non ha mai scritto nei canali conteggiati
            if number < 0:
                return
            afler = Afler.new_entry(member.display_name)
            afler.modify_warn(number)
            self.archive.add(member.id, afler)
        self.archive.save()


async def setup(bot: commands.Bot):
    """Entry point per il caricamento della cog"""
    await bot.add_cog(ModerationCog(bot))
