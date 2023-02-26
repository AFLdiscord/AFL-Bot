"""Modulo per l'interazione con le API di reddit, utilizzate per alcuni comandi"""
from json import load
import os
from typing import Dict

import discord
from discord.ext import commands
from asyncpraw import Reddit
from asyncpraw.models import ListingGenerator, Submission
from aflbot import AFLBot
from utils.archive import Archive
from utils.bot_logger import BotLogger
from utils.config import Config
from utils import shared_functions as sf


def is_moderator():
    """Decoratore che permette di separare i comandi per gli utenti dai
    comandi per i moderatori.
    """
    async def mod(ctx: commands.Context):
        assert isinstance(ctx.author, discord.Member)
        return any(role in Config.get_config().moderation_roles for role in ctx.author.roles)
    return commands.check(mod)


class RedditCog(commands.Cog):
    """Raccoglie i comandi che richiedono interazione con reddit."""

    def __init__(self, bot: AFLBot) -> None:
        self.bot: AFLBot = bot
        self.archive: Archive = Archive.get_instance()
        self.logger: BotLogger = BotLogger.get_instance()
        self.config: Config = Config.get_config()
        # initialize the reddit instance, need specific user agent
        self.reddit: Reddit = Reddit(
            client_id=os.getenv('REDDIT_APP_ID'),
            client_secret=os.getenv('REDDIT_APP_SECRET'),
            user_agent=f'discord:AFL-Bot:{self.bot.version} (by /u/Skylake-dev)'
        )
        self.post_caches: Dict[str, ListingGenerator] = {}
        try:
            with open('subreddits.json', 'r') as f:
                self.subs = load(f)
        except FileNotFoundError:
            self.subs = ['4chan']

    def cog_check(self, ctx: commands.Context):
        """Check sui comandi per autorizzarne l'uso solo agli AFL"""
        if not isinstance(ctx.author, discord.Member):
            return False
        for role in ctx.author.roles:
            if self.config.afl_role_id == role.id:
                return True
        return False

    @commands.hybrid_group(name='rdm', with_app_command=True, fallback='show')
    async def reddit_manager(self, ctx: commands.Context):
        """Gruppo di comandi per gestire i subreddit ammessi.
        Se chiamato senza nessun'altro argomento, mostra i subreddit
        correntemente accettati.
        """
        if len(self.subs) > 0:
            await ctx.reply(', '.join(self.subs))
        else:
            await ctx.reply('Lista dei subreddit vuota.')

    @reddit_manager.command(brief='aggiunge un subreddit alla lista dei subreddit ammessi')
    @is_moderator()
    async def add(self, ctx: commands.Context, name: str) -> None:
        """Aggiunge un subreddit alla lista dei subreddit ammessi.

        :param name: il nome del subreddit da aggiungere
        """
        if name in self.subs:
            await ctx.reply(f'`{name}` già presente nella lista dei subreddit.')
        else:
            self.subs.append(name)
            await ctx.reply(f'`{name}` aggiunto alla lista dei subreddit.')
            sf.update_json_file(self.subs, 'subreddits.json')

    @reddit_manager.command(brief='aggiunge un subreddit alla lista dei subreddit ammessi')
    @is_moderator()
    async def remove(self, ctx: commands.Context, name: str) -> None:
        """Rimuove un subreddit alla lista dei subreddit ammessi.

        :param name: il nome del subreddit da rimuovere
        """
        if name not in self.subs:
            await ctx.reply(f'`{name}` non è nella lista dei subreddit.')
        else:
            self.subs.remove(name)
            await ctx.reply(f'`{name}` rimosso dalla lista dei subreddit.')
            sf.update_json_file(self.subs, 'subreddits.json')


    @commands.hybrid_command(brief='ritorna un post da 4chan', aliases=['4chan', '4c'])
    async def fourchan(self, ctx: commands.Context):
        """Ritorna un post dal subreddit r/4chan.

        Sintassi
        <4chan      # ritorna un'embed con l'immagine
        """
        await self.post_submission(ctx, '4chan')

    async def post_submission(self, ctx: commands.Context, sub: str) -> None:
        """Pubblica un post del subreddit richiesto.

        :param ctx: il contesto del comando che ha richiesto il post
        :param sub: il subreddit di interesse
        """
        # TODO: supporto video
        submission = await self.load_post(sub)
        media: list[discord.Embed] = []
        if 'gallery' in submission.url:
            # Il post ha una galleria di contenuti multimediali
            for item in sorted(submission.gallery_data['items'], key=lambda x: x['id']):
                media_id = item['media_id']
                meta = submission.media_metadata[media_id]
                if meta['e'] == 'Image':
                    # ad esempio, 'jpg' in 'image/jpg'
                    extension = meta['m'][6:]
                    embed = discord.Embed(
                        # limit embed title is 256 chars
                        title=submission.title[:256],
                        url=f'https://www.reddit.com{submission.permalink}',
                        description="",
                        color=discord.Color.green()
                    )
                    embed.set_image(
                        url=f'https://i.redd.it/{media_id}.{extension}')
                    media.append(embed)
        else:
            # Il post ha una sola immagine
            post = discord.Embed(
                title=submission.title[:256],
                url=f"https://www.reddit.com{submission.permalink}",
                description="",
                color=discord.Color.green()
            )
            post.set_image(url=submission.url)
            media.append(post)
        await ctx.send(embeds=media)

    async def create_post_iterator(self, sub: str) -> None:
        """Prepara un AsyncIterator per caricare i post.

        :param sub: il subreddit da cui caricare i post
        """
        subreddit = await self.reddit.subreddit(sub)
        # arbitrary limit, i guess that after these have been consumed hot posts will change
        self.post_caches[sub] = subreddit.hot(limit=100)

    async def load_post(self, sub: str) -> Submission:
        """Carica un post dal sub indicato.

        :param sub: il subreddit da cui caricare il post

        :returns: il post
        :rtype: asyncpraw.models.Submission
        """
        try:
            generator = self.post_caches[sub]
        except KeyError:
            await self.create_post_iterator(sub)
            generator = self.post_caches[sub]
        while True:
            try:
                submission = await generator.__anext__()
                # in python 3.10+ --> submission = await anext(self.post_cache[sub])
            except StopAsyncIteration:
                await self.create_post_iterator(sub)
                submission = await generator.__anext__()
            if not submission.stickied:
                return submission


async def setup(bot: AFLBot):
    """Entry point per il caricamento della cog."""
    if (not os.getenv('REDDIT_APP_ID')) or (not os.getenv('REDDIT_APP_SECRET')):
        print('chiavi di reddit non trovate, carico fallback')
        await bot.add_cog(RedditCogFallback(bot))
    else:
        await bot.add_cog(RedditCog(bot))


class RedditCogFallback(commands.Cog):

    def __init__(self, bot: AFLBot) -> None:
        self.bot: AFLBot = bot

    @commands.hybrid_command(brief='ritorna un post da 4chan', aliases=['4chan', '4c'])
    async def fourchan(self, ctx: commands.Context):
        await self.reply(ctx)

    async def reply(self, ctx: commands.Context):
        await ctx.send(
            'Per usare questo comando è necessario aggiungere le chiavi '
            'delle API di reddit. Segui le istruzioni nel readme per farlo.'
        )
