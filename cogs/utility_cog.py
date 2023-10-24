""":class: UtilityCog contiene comandi di uso generale."""
import hashlib
from datetime import date, datetime, timedelta
from enum import Enum
from git.repo import Repo
from typing import Optional, Union

import discord
from discord.ext import commands
from aflbot import AFLBot
from utils.afler import Afler
from utils.archive import Archive
from utils.banned_words import BannedWords
from utils.bot_logger import BotLogger
from utils.config import Config


class UtilityCog(commands.Cog, name='Utility'):
    """Contiene i comandi destinati ad essere usati dagli AFL con funzionalità varie.
    Tutti i comandi sono utilizzabili sia da messaggio che come slash command.
    - status ritorna lo status del membro citato
    - avatar ritorna la foto profilo dell'utente citato
    - setnick permette di cambiare nickname periodicamente
    - setbio imposta la propria bio
    - bio ritorna la bio dell'utente citato
    - leaderboard mostra il numero di messaggi mandati dagli aflers
    - info invia il link alla pagina GitHub di AFL
    - hash permette di calcolare l'hash dell'input
    """

    def __init__(self, bot: AFLBot):
        self.bot: AFLBot = bot
        self.archive: Archive = Archive.get_instance()
        self.logger: BotLogger = BotLogger.get_instance()
        self.config: Config = Config.get_config()

    def cog_check(self, ctx: commands.Context):
        """Check sui comandi per autorizzarne l'uso solo agli AFL"""
        if not isinstance(ctx.author, discord.Member):
            return False
        for role in ctx.author.roles:
            if self.config.afl_role_id == role.id:
                return True
        return False

    @commands.hybrid_command(brief='ritorna statistiche sul membro menzionato')
    async def status(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Mostra il proprio status oppure quello del membro fornito come parametro tramite embed.
        Lo status comprende:
        - numero di messaggi inviati nell'ultimo periodo (nella finestra temporale)
        - possesso dei ruoli e relativa scadenza (assente per i mod)
        - numero di violazioni e relativa scadenza

        Sintassi:
        <status             ritorna lo status del chiamante
        <status @someone    ritorna lo status di 'someone' se presente nel file
        """
        if member is None:
            assert isinstance(ctx.author, discord.Member)
            member = ctx.author
        try:
            item: Afler = self.archive.get(member.id)
        except KeyError:
            await self.logger.log(f'richiesto status di {member.mention} ma non è presente nell\'archivio')
            await ctx.send('l\'utente indicato non è registrato', delete_after=5)
            await ctx.message.delete(delay=5)
            return
        status = discord.Embed(
            title=f'Status di {item.escaped_nick}',
            color=member.top_role.color
        )
        status.set_thumbnail(url=member.display_avatar)
        msg_text = f'Oratore: {item.count_orator_messages()}\nCazzaro: {item.dank_messages_buffer}\nTotale: {item.count_orator_messages()+item.dank_messages_buffer}'
        status.add_field(name='Messaggi ultimi 7 giorni:',
                         value=msg_text, inline=False)
        msg_text = f'Oratore: {item.orator_total_messages}\nCazzaro: {item.dank_total_messages}\nTotale: {item.total_messages}'
        status.add_field(name='Messaggi totali:',
                         value=msg_text, inline=False)
        is_a_mod = False
        for role in member.roles:
            if role.id in self.config.moderation_roles_id:
                is_a_mod = True
                status.add_field(name='Ruolo:', value=role.name, inline=False)
                break
        if not is_a_mod and item.orator:
            assert item.orator_expiration is not None
            status.add_field(
                name='Oratore:', value=f'scade il {date.strftime(item.orator_expiration, "%d/%m")}', inline=False)
        if item.dank:
            assert item.dank_expiration is not None
            status.add_field(
                name='Cazzaro:', value=f'scade il {datetime.strftime(item.dank_expiration, "%d/%m %H:%M")}', inline=False)
        if item.warn_count() == 0:
            status.add_field(name='Violazioni:', value='0', inline=False)
        else:
            if item.last_violation_date != None:
                violations_expiration = (
                    item.last_violation_date + timedelta(days=self.config.violations_reset_days)).isoformat()
                status.add_field(
                    name='Violazioni:', value=f'{item.warn_count()} (scade il {violations_expiration})', inline=False)
        await ctx.send(embed=status)

    @commands.hybrid_command(brief='invia la propic dell\'utente')
    async def avatar(self, ctx: commands.Context, user: Optional[Union[discord.User, discord.Member]] = None):
        """Invia la propria propic o quella dell'utente menzionato. Non è necessario che l'utente
        faccia parte del server, basta che la menzione sia valida.

        Sintassi:
        <avatar             # invia la propria propic
        <avatar @someone    # invia la propic di 'someone'
        """
        if user is None:
            user = ctx.author
        # se l'utente è nel server, stampo il suo nickname invece del suo username
        member = self.config.guild.get_member(user.id)
        if member is not None:
            user = member
        avatar = discord.Embed(
            title=f'Avatar di {discord.utils.escape_markdown(user.display_name)}:'
        )
        avatar.set_image(url=user.display_avatar)
        await ctx.send(embed=avatar)

    @commands.hybrid_command(brief='permette di cambiare nickname periodicamente', hidden=True)
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
        last_change = item.last_nick_change
        difference = date.today() - last_change
        if difference.days < self.config.nick_change_days:
            renewal = datetime.combine(last_change + timedelta(days=self.config.nick_change_days), datetime.min.time())
            await ctx.send(f'Prossimo cambio il {discord.utils.format_dt(renewal, "D")}')
        elif BannedWords.contains_banned_words(new_nick):
            await ctx.send('Il nickname non può contenere parole offensive')
        elif len(new_nick) > 32:
            await ctx.send('La lunghezza massima del nickname è di 32 caratteri')
        elif self.archive.contains_nick(new_nick):
            await ctx.send('Questo nickname è già in uso')
        elif any(ctx.author.id != afler and new_nick == self.bot.get_user(afler).name for afler in self.archive.keys()):  # type: ignore
            await ctx.send('Questo nickname è l\'username di un utente, non puoi usarlo')
        else:
            old_nick = discord.utils.escape_markdown(ctx.author.display_name)
            item.nick = new_nick
            self.archive.save()
            escaped_nick = discord.utils.escape_markdown(
                new_nick)   # serve per stampare
            await ctx.author.edit(nick=escaped_nick)    # type: ignore
            await ctx.send(f'Nickname cambiato in {escaped_nick}')
            await self.logger.log(f'Nickname di {ctx.author.mention} modificato in {escaped_nick} (era {old_nick})')

    @commands.hybrid_command(brief='imposta la propria bio')
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
        await self.logger.log(f'aggiunta bio di {ctx.author.mention}')
        await ctx.send('Bio aggiunta correttamente.')

    @commands.hybrid_command(brief='ritorna la bio dell\'utente citato')
    async def bio(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Ritorna la propria bio o quella dell'utente citato. Usare
        <setbio per impostare la propria bio

        Sintassi:
        <bio               # ritorna la propria bio
        <bio @someone      # ritorna la bio di *someone*, se presente
        """
        if member is None:
            assert isinstance(ctx.author, discord.Member)
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
                title=f'Bio di {item.escaped_nick}',
                description=item.bio,
                color=member.top_role.color
            )
            await ctx.send(embed=bio)

    class Category(Enum):
        oratore = 'oratore'
        cazzaro = 'cazzaro'
        generale = 'generale'

        def str(self) -> str:
            return self.value

    @commands.hybrid_command(brief='mostra il numero di messaggi mandati dagli aflers')
    @discord.app_commands.rename(category='categoria')
    @discord.app_commands.describe(
        category='la categoria della classifica'
    )
    async def leaderboard(self, ctx: commands.Context, category: Category = Category.generale):
        """Mostra la classifica degli afler in base alla classifica scelta.

        Sintassi
        <leaderboard     # stampa la leaderboard
        """
        assert isinstance(category, self.Category)
        ranking = []
        for id in self.archive.keys():
            afler = self.archive.get(id)
            mention = f'<@{id}>'
            if category == self.Category.generale:
                message_count = afler.total_messages
            elif category == self.Category.oratore:
                message_count = afler.orator_total_messages
            elif category == self.Category.cazzaro:
                message_count = afler.dank_total_messages
            if message_count > 0:
                ranking.append((mention, message_count))
        ranking = sorted(ranking, key=lambda i: i[1], reverse=True)
        leaderboard = ''
        for i, entry in enumerate(ranking, start=1):
            leaderboard += f'{i}) {entry[0]} - {entry[1]}\n'
        embed = discord.Embed(title=f'Leaderboard {category.value}')
        embed.description = leaderboard
        await ctx.send(embed=embed)

    @commands.hybrid_command(brief='uptime e link alla pagina GitHub di AFL')
    async def info(self, ctx: commands.Context):
        """Uptime e link alla pagina GitHub di AFL.

        Sintassi
        <info         # invia le info
        """
        assert isinstance(self.bot.user, discord.ClientUser)
        embed = discord.Embed(title='Informazioni sul bot')
        embed.add_field(
            name='Uptime',
            value=f'{datetime.now() - self.bot.start_time}',
            inline=False
        ).add_field(
            name='Link organizzazione',
            value='https://github.com/AFLdiscord',
            inline=False
        ).set_thumbnail(
            url=self.bot.user.display_avatar
        ).set_footer(
            text=f'AFL Bot versione {self.bot.version} - {Repo(".").head.commit.hexsha[0:7]}',
        )
        await ctx.send(embed=embed)

    class HashFunctions(Enum):
        md5 = hashlib.md5
        sha1 = hashlib.sha1
        sha224 = hashlib.sha224
        sha256 = hashlib.sha256
        sha384 = hashlib.sha384
        sha512 = hashlib.sha512
        sha3_224 = hashlib.sha3_224
        sha3_256 = hashlib.sha3_256
        sha3_384 = hashlib.sha3_384
        sha3_512 = hashlib.sha3_512

    @discord.app_commands.command(description='Calcolo di varie funzioni di hash')
    @discord.app_commands.rename(hash_type='hash', input='input')
    @discord.app_commands.describe(
        hash_type='funzione di hash da calcolare',
        input='stringa di cui calcolare l\'hash (encoding utf-8)'
    )
    async def hash(self, interaction: discord.Interaction, hash_type: HashFunctions, input: str):
        """Comando per calcolare l'hash di un dato input.

        Supporta diversi algoritmi:
         - md5
         - sha1
         - sha224
         - sha256
         - sha384
         - sha512
         - sha3_224
         - sha3_256
         - sha3_384
         - sha3_512

        Sintassi
        /hash sha256 The SHA256 for this sentence begins with: one, eight, two, a, seven, c and nine.
        """
        assert isinstance(hash_type, self.HashFunctions)
        assert type(interaction.channel) is discord.TextChannel
        response = discord.Embed(
            title='Calcolo hash',
            colour=discord.Colour.green()
        )
        response.add_field(
            name='Input', value=input, inline=False
        ).add_field(
            name=hash_type.name.upper(),
            value=f'`{hash_type.value(bytes(input, "utf-8")).hexdigest()}`',
            inline=False
        )
        await interaction.response.send_message(embed=response)


async def setup(bot: AFLBot):
    """Entry point per il caricamento della cog."""
    await bot.add_cog(UtilityCog(bot))
