import json
import discord
from discord.ext import commands
from datetime import datetime, timedelta
from cogs import sharedFunctions
from cogs.sharedFunctions import BannedWords, Config

"""Contiene i comandi destinati ad essere usati da tutti con funzionalità varie:
- status ritorna lo status del membro citato
- avatar ritorna la foto profilo dell'utente citato
"""

class UtilityCog(commands.Cog, name='Utility'):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief="ritorna statistiche sul membro menzionato")
    async def status(self, ctx, member: discord.Member = None):
        """Mostra il proprio status oppure quello del membro fornito come parametro tramite embed.
        Lo status comprende:
        - numero di messaggi degli ultimi 7 giorni
        - data ultimo messaggio conteggiato (inviato nei canali da contare)
        - possesso del ruolo attivo e relativa scadenza (assente per i mod)
        - numero di violaizoni e relativa scadenza
        
        Sintassi:
        <status             ritorna lo status del chiamante
        <status @someone    ritorna lo status di someone se presente nel file
        """
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
        if item["last_message_date"] is None:
            status.add_field(name='Messaggi ultimi 7 giorni:', value='0', inline=False)
        else: 
            status.add_field(name='Messaggi ultimi 7 giorni:', value=str(sharedFunctions.count_messages(item)) +
                ' (ultimo il ' + item["last_message_date"] + ')', inline=False)  
        is_a_mod = False
        for role in member.roles:
            if role.id in Config.config['moderation_roles_id']:
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
                timedelta(days=Config.config["violations_reset_days"])).__str__()
            status.add_field(name='Violazioni:', value=str(item["violations_count"]) +
                ' (scade il ' + violations_expiration + ')', inline=False)
        await ctx.send(embed=status)

    @commands.command(brief='invia la propic dell\'utente')
    async def avatar(self, ctx, user: discord.User = None):
        """Invia la propria propic o quella dell'utente menzionato. Non è necessario che l'utente faccia
        parte del server basta che la menzione sia valida.

        Sintassi:
        <avatar             invia la propria propic
        <avatar @someone    invia la propic di someone
        """
        if user is None:
            user = ctx.author
        #se l'utente è nel server, stampo il suo nickname invece del suo username
        member = self.bot.get_guild(Config.config['guild_id']).get_member(user.id)
        if member is not None:
            user = member
        avatar = discord.Embed(
            title=f'Avatar di {user.display_name}:'
        )
        avatar.set_image(url=user.avatar_url)
        await ctx.send(embed=avatar)

def setup(bot):
    bot.add_cog(UtilityCog(bot))