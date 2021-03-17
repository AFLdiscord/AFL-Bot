import json
import discord
from discord.ext import commands
from datetime import datetime, timedelta
from cogs import sharedFunctions

"""contiene i comandi di uso generale:
- status
- avatar
"""

class UtilityCog(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.GUILD_ID = int(config['guild_id'])
        self.MODERATION_ROLES_ID = []
        for mod in config['moderation_roles_id']:
            self.MODERATION_ROLES_ID.append(int(mod))
        self.VIOLATIONS_RESET_DAYS = config["violations_reset_days"]

    @commands.command()
    async def status(self, ctx, member:discord.Member = None):
        """mostra il proprio status oppure quello del membro fornito come parametro"""
        if member is None:
            member = ctx.author
        try:
            with open('aflers.json','r') as file:
                prev_dict = json.load(file)
        except FileNotFoundError:
            await ctx.send('nessun elenco', delete_after=5)
            await ctx.message.delete(delay=5)
            return
        try:
            item = prev_dict[str(member.id)]
        except KeyError:
            print('non presente')
            await ctx.send('l\'utente indicato non è registrato', delete_after=5)
            await ctx.message.delete(delay=5)
            return
        status = discord.Embed(
            title=f'Status di {member.display_name}',
            color=member.top_role.color
        )
        status.set_thumbnail(url=member.avatar_url)
        status.add_field(name='Messaggi ultimi 7 giorni:', value=str(sharedFunctions.count_messages(item)), inline=False)
        is_a_mod = False
        for role in member.roles:
            if role.id in self.MODERATION_ROLES_ID:
                is_a_mod = True
                status.add_field(name='Ruolo:', value=role.name, inline=False)
                break
        if not is_a_mod:
            if item["active"] == False:
                status.add_field(name='Attivo:', value='no', inline=False)
            else:
                status.add_field(name='Attivo:', value='sì (scade il ' + item["expiration"] + ')', inline=False)
        if item["violations_count"] == 0:
            status.add_field(name='Violazioni:', value='0', inline=False)
        else:
            violations_expiration = datetime.date(datetime.strptime(item["last_violation_count"], '%Y-%m-%d') +
                timedelta(days=self.VIOLATIONS_RESET_DAYS)).__str__()
            status.add_field(name='Violazioni:', value=str(item["violations_count"]) +
                ' (scade il ' + violations_expiration + ')', inline=False)
        await ctx.send(embed=status)

    @commands.command()
    async def avatar(self, ctx, user: discord.User = None):
        """invia sulla chat la pfp dell'utente menzionato, indipendentemente dal fatto che l'utente sia
        un membro del server o meno
        """
        if user is None:
            user = ctx.author
        #se l'utente è nel server, stampo il suo nickname invece del suo username
        member = self.bot.get_guild(self.GUILD_ID).get_member(user.id)
        if member is not None:
            user = member
        avatar = discord.Embed(
            title=f'Avatar di {user.display_name}:'
        )
        avatar.set_image(url=user.avatar_url)
        await ctx.send(embed=avatar)

def setup(bot):
    try:
        with open('config.json', 'r') as file:
            config = json.load(file)
    except FileNotFoundError:
        print('crea il file config.json seguendo le indicazioni del template')
        exit()
    bot.add_cog(UtilityCog(bot, config))