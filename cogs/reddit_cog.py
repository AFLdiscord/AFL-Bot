"""Modulo per l'interazione con le API di reddit, utilizzate per alcuni comandi"""
import os
import discord
from dotenv import load_dotenv
from discord.ext import commands
from discord.utils import MISSING
from asyncpraw import Reddit
from asyncpraw.models import ListingGenerator
from aflbot import AFLBot
from utils.archive import Archive
from utils.bot_logger import BotLogger
from utils.config import Config


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
        self.post_cache: ListingGenerator = MISSING

    def cog_check(self, ctx: commands.Context):
        """Check sui comandi per autorizzarne l'uso solo agli AFL"""
        if not isinstance(ctx.author, discord.Member):
            return False
        for role in ctx.author.roles:
            if self.config.afl_role_id == role.id:
                return True
        return False

    @commands.hybrid_command(brief='ritorna un post da 4chan', aliases=['4chan', '4c'])
    async def fourchan(self, ctx: commands.Context):
        """Ritorna un post dal subreddit r/4chan.

        Sintassi
        <4chan      # ritorna un'embed con l'immagine
        """
        if self.post_cache is MISSING:
            await self._load_posts('4chan')
        # in python 3.10+ --> submission = await anext(self.post_cache)
        try:
            submission = await self.post_cache.__anext__()
        except StopAsyncIteration:
            await self._load_posts('4chan')
            submission = await self.post_cache.__anext__()
        # limit embed title is 256 chars
        post = discord.Embed(
            title=submission.title[:256],
            url=f"https://www.reddit.com{submission.permalink}",
            description="", color=discord.Color.green()
        )
        post.set_image(url=submission.url)
        await ctx.send(embed=post)

    async def _load_posts(self, sub: str) -> None:
        """Prepara un AsyncIterator per caricare i post.

        :param sub: il subreddit da cui caricare i post
        """
        subreddit = await self.reddit.subreddit(sub)
        # arbitrary limit, i guess that after these have been consumed hot posts will change
        self.post_cache = subreddit.hot(limit=100)


async def setup(bot: AFLBot):
    """Entry point per il caricamento della cog."""
    # load reddit data from .env
    load_dotenv()
    await bot.add_cog(RedditCog(bot))
