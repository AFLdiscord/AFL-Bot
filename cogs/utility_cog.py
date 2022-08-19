""":class: UtilityCog contiene comandi di uso generale."""
from datetime import datetime, timedelta
from typing import Optional, Tuple

import discord
from discord.ext import commands
from utils.shared_functions import Afler, Archive, BannedWords, BotLogger, Config


class UtilityCog(commands.Cog, name='Utility'):
    """Contiene i comandi destinati ad essere usati dagli AFL con funzionalità varie:
    - status ritorna lo status del membro citato
    - avatar ritorna la foto profilo dell'utente citato
    - setnick permette di cambiare nickname periodicamente
    - setbio imposta la propria bio
    - bio ritorna la bio dell'utente citato
    - showactive ritorna l'elenco dei canali conteggiati per l'attivo
    - leaderboard mostra il numero di messaggi mandati dagli aflers
    - info invia il link alla pagina GitHub di AFL
    """

    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.archive: Archive = Archive.get_instance()
        self.logger: BotLogger = BotLogger.get_instance()
        self.config: Config = Config.get_config()

    def cog_check(self, ctx: commands.Context):
        """Check sui comandi per autorizzarne l'uso solo agli AFL"""
        for role in ctx.author.roles:
            if self.config.afl_role_id == role.id:
                return True
        return False

    @commands.command(brief='ritorna statistiche sul membro menzionato')
    async def status(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Mostra il proprio status oppure quello del membro fornito come parametro tramite embed.
        Lo status comprende:
        - numero di messaggi degli ultimi 7 giorni
        - data ultimo messaggio conteggiato (inviato nei canali da contare)
        - possesso del ruolo attivo e relativa scadenza (assente per i mod)
        - numero di violaizoni e relativa scadenza

        Sintassi:
        <status             ritorna lo status del chiamante
        <status @someone    ritorna lo status di 'someone' se presente nel file
        """
        if member is None:
            member = ctx.author
        try:
            item: Afler = self.archive.get(member.id)
        except KeyError:
            await self.logger.log(f'richiesto status di {member.display_name} ma non è presente nell\'archivio')
            await ctx.send('l\'utente indicato non è registrato', delete_after=5)
            await ctx.message.delete(delay=5)
            return
        status = discord.Embed(
            title=f'Status di {member.display_name}',
            color=member.top_role.color
        )
        status.set_thumbnail(url=member.avatar_url)
        if item.last_message_date() is None:
            status.add_field(name='Messaggi ultimi 7 giorni:',
                             value='0', inline=False)
        else:
            status.add_field(name=f'Messaggi ultimi 7 giorni:', value=f'{item.count_messages()} (ultimo il {item.last_message_date()})', inline=False)
        is_a_mod: bool = False
        for role in member.roles:
            if role.id in self.config.moderation_roles_id:
                is_a_mod = True
                status.add_field(name='Ruolo:', value=role.name, inline=False)
                break
        if not is_a_mod:
            if not item.active:
                status.add_field(name='Attivo:', value='no', inline=False)
            else:
                status.add_field(name='Attivo:', value=f'sì (scade il {item.active_expiration()})', inline=False)
        if item.warn_count() == 0:
            status.add_field(name='Violazioni:', value='0', inline=False)
        else:
            if item.last_violations_count() != None:
                violations_expiration = (item.last_violations_count(
                ) + timedelta(days=self.config.violations_reset_days)).__str__()
                status.add_field(name='Violazioni:', value=f'{item.warn_count()} (scade il {violations_expiration})', inline=False)
        await ctx.send(embed=status)

    @commands.command(brief='invia la propic dell\'utente')
    async def avatar(self, ctx: commands.Context, user: Optional[discord.User] = None):
        """Invia la propria propic o quella dell'utente menzionato. Non è necessario che l'utente
        faccia parte del server, basta che la menzione sia valida.

        Sintassi:
        <avatar             # invia la propria propic
        <avatar @someone    # invia la propic di 'someone'
        """
        if user is None:
            user = ctx.author
        # se l'utente è nel server, stampo il suo nickname invece del suo username
        member = self.bot.get_guild(self.config.guild_id).get_member(user.id)
        if member is not None:
            user = member
        avatar = discord.Embed(
            title=f'Avatar di {user.display_name}:'
        )
        avatar.set_image(url=user.avatar_url)
        await ctx.send(embed=avatar)

    @commands.command(brief='permette di cambiare nickname periodicamente', hidden=True)
    async def setnick(self, ctx: commands.Context, *, new_nick: str):
        """Permette di cambiare il proprio nickname periodicamente. La frequenza con
        cui è possibile farlo è definita nel config. Impedisce che due membri abbiano lo
        lo stesso nickname.

        Sintassi:
        <setnick afler       # cambia il nickname in afler
        <setnick due aflers  # può contenere anche più parole
        """
        try:
            item: Afler = self.archive.get(ctx.author.id)
        except KeyError:
            await ctx.send('Non tovato nel file :(', delete_after=5)
            return
        # se new_nick è uguale al nickname attuale, non elaboro oltre
        if item.nick == new_nick:
            await ctx.send('Il nickname coincide con quello attuale')
            return
        last_change = item.last_nick_change()
        difference = datetime.date(datetime.now()) - last_change
        if difference.days < self.config.nick_change_days:
            renewal = last_change + \
                timedelta(days=self.config.nick_change_days)
            days_until_renewal = renewal - datetime.date(datetime.now())
            await ctx.send(f'Prossimo cambio tra {days_until_renewal.days} giorni')
        elif BannedWords.contains_banned_words(new_nick):
            await ctx.send('Il nickname non può contenere parole offensive')
        elif len(new_nick) > 32:
            await ctx.send('La lunghezza massima del nickname è di 32 caratteri')
        elif self.archive.contains_nick(new_nick):
            await ctx.send('Questo nickname è già in uso')
        elif any(ctx.author.id != afler and new_nick == self.bot.get_user(afler).name for afler in self.archive.keys()):
            await ctx.send('Questo nickname è l\'username di un utente, non puoi usarlo')
        else:
            old_nick = ctx.author.display_name
            item.nick = new_nick
            self.archive.save()
            await ctx.author.edit(nick=new_nick)
            await ctx.send(f'Nickname cambiato in {new_nick}')
            await self.logger.log(f'Nickname di {ctx.author.mention} modificato in `{new_nick}` (era `{old_nick}`)')

    @commands.command(brief='imposta la propria bio')
    async def setbio(self, ctx: commands.Context, *, bio: str):
        """Permette di impostare una biografia visibile agli altri membri.
        Non sono ovviamente ammesse parole vietate e gli admin si riservano il
        diritto di editare quelle ritenute offensive.

        Sintassi:
        <setbio mia bio    # imposta *mia bio* come bio
        """
        if len(bio) > self.config.bio_length_limit:
            await ctx.send(f'Bio troppo lunga, il limite è {self.config.bio_length_limit} caratteri.')
            return
        if BannedWords.contains_banned_words(bio):
            return
        try:
            item: Afler = self.archive.get(ctx.author.id)
        except KeyError:
            await ctx.send('Non tovato nel file :(', delete_after=5)
            return
        item.bio = bio
        self.archive.save()
        await self.logger.log(f'aggiunta bio di {ctx.author.display_name}')
        await ctx.send('Bio aggiunta correttamente.')

    @commands.command(brief='ritorna la bio dell\'utente citato')
    async def bio(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Ritorna la propria bio o quella dell'utente citato. Usare
        <setbio per impostare la propria bio

        Sintassi:
        <bio               # ritorna la propria bio
        <bio @someone      # ritorna la bio di *someone*, se presente
        """
        if member is None:
            member = ctx.author
        try:
            item: Afler = self.archive.get(member.id)
        except KeyError:
            await ctx.send('Non tovato nel file :(', delete_after=5)
            return
        if item.bio is None:
            await ctx.send('L\'utente selezionato non ha una bio.')
        else:
            bio = discord.Embed(
                title=f'Bio di {member.display_name}',
                description=item.bio,
                color=member.top_role.color
            )
            await ctx.send(embed=bio)

    @commands.command(brief='ritorna l\'elenco dei canali conteggiati per l\'attivo')
    async def showactive(self, ctx: commands.Context):
        """Ritorna l'elenco dei canali in cui i messaggi vengono conteggiati
        al fine di assegnare il ruolo attivo.

        Sintassi:
        <showactive     # ritorna l'elenco
        """
        channels = 'Elenco canali conteggiati per l\'attivo:\n'
        channels += '\n'.join([f'<#{id}>' for id in self.config.active_channels_id])
        await ctx.send(channels)

    @commands.command(brief='mostra il numero di messaggi mandati dagli aflers')
    async def leaderboard(self, ctx: commands.Context):
        """Mostra la classifica degli afler in base ai messaggi degli ultimi
        7 giorni. Solo i membri con più di 0 messaggi sono mostrati.
        
        Sintassi
        <leaderboard     # stampa la leaderboard
        """
        ranking = []
        for id in self.archive.keys():
            afler = self.archive.get(id)
            mention = f'<@{id}>'
            message_count = afler.count_messages()
            if message_count > 0:
                ranking.append((mention, message_count))
        ranking = sorted(ranking, key= lambda i: i[1], reverse=True)
        leaderboard = ''
        for i in range(len(ranking)):
            entry = ranking[i]
            leaderboard += f'{i+1}) {entry[0]} - {entry[1]}\n'
        embed = discord.Embed(title='Leaderboard')
        embed.description = leaderboard
        await ctx.send(embed=embed)

    @commands.command(brief='invia il link alla pagina GitHub di AFL')
    async def info(self, ctx: commands.Context):
        """Invia il link alla pagina GitHub di AFL.
        
        Sintassi
        <info         # invia il link
        """
        await ctx.send('https://github.com/AFLdiscord')


def setup(bot: commands.Bot):
    """Entry point per il caricamento della cog."""
    bot.add_cog(UtilityCog(bot))
