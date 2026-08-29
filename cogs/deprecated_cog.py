from discord.ext import commands

from aflbot import AFLBot

# Lista dei comandi deprecati, da espandere man mano.
deprecated_commands = [
]

class CommandDeprecatorMeta(commands.CogMeta):
    """Metaclasse impiegata per iniettare i comandi nel namespace della cog.

    In questo modo è possibile enumerare i comandi a runtime, anziché
    creare una callback per ogni vecchio comando.
    """
    def __new__(mcls, name, bases, namespace, **kwargs):
        for command_name in deprecated_commands:
            # creo una funzione che chiama il metodo della cog
            async def cmd(self, ctx):
                await self.deprecation_notice(ctx)

            # rimpiazzo nome e nome qualificato con quello del vecchio comando
            cmd.__name__ = command_name
            cmd.__qualname__ = f'{name}.{command_name}'
            # lo aggiungo manualmente al suo namespace
            namespace[command_name] = commands.command(name=command_name)(cmd)

        return super().__new__(mcls, name, bases, namespace, **kwargs)


class CommandDeprecatorCog(
    commands.Cog,
    metaclass=CommandDeprecatorMeta,
):
    """Cog che contiene le callback per i vecchi comandi.

    Per aggiungere un comando, basta aggiungerlo alla lista `deprecated_commands`
    sopra. I comandi che che richiedono un messaggio particolare possono
    essere invece aggiunti esplicitamente sotto (vedi setnick).
    """

    def __init__(self, bot: AFLBot):
        self.bot = bot

    async def deprecation_notice(self, ctx: commands.Context):
        """Callback generica dei vecchi comandi."""
        await ctx.reply("Comando deprecato, usa la versione slash.")


    @commands.command(hidden=True)
    async def setnick(self, ctx: commands.Context):
        await ctx.reply('Comando deprecato, usa `/nick`.')


async def setup(bot: AFLBot):
    await bot.add_cog(CommandDeprecatorCog(bot))
