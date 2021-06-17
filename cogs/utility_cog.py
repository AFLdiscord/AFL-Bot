""":class: UtilityCog contiene comandi di uso generale."""
import json
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from utils import shared_functions
from utils.shared_functions import Config, BannedWords

class UtilityCog(commands.Cog, name='Utility'):
    """Contiene i comandi destinati ad essere usati dagli AFL con funzionalità varie:
    - status ritorna lo status del membro citato
    - avatar ritorna la foto profilo dell'utente citato
    - setnick permette di cambiare nickname periodicamente
    - setbio imposta la propria bio
    - bio ritorna la bio dell'utente citato
    """
    def __init__(self, bot):
        self.bot = bot

    def cog_check(self, ctx):
        """Check sui comandi per autorizzarne l'uso solo agli AFL"""
        for role in ctx.author.roles:
            if Config.config['afl_role_id'] == role.id:
                return True
        return False

    @commands.command(brief='ritorna statistiche sul membro menzionato')
    async def status(self, ctx, member: discord.Member = None):
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
        if item['last_message_date'] is None:
            status.add_field(name='Messaggi ultimi 7 giorni:', value='0', inline=False)
        else:
            status.add_field(name='Messaggi ultimi 7 giorni:', value=str(shared_functions.count_messages(item)) +
                ' (ultimo il ' + item['last_message_date'] + ')', inline=False)
        is_a_mod = False
        for role in member.roles:
            if role.id in Config.config['moderation_roles_id']:
                is_a_mod = True
                status.add_field(name='Ruolo:', value=role.name, inline=False)
                break
        if not is_a_mod:
            if not item['active']:
                status.add_field(name='Attivo:', value='no', inline=False)
            else:
                status.add_field(name='Attivo:', value='sì (scade il ' + item['expiration'] + ')', inline=False)
        if item['violations_count'] == 0:
            status.add_field(name='Violazioni:', value='0', inline=False)
        else:
            violations_expiration = datetime.date(datetime.strptime(item['last_violation_count'], '%Y-%m-%d') +
                timedelta(days=Config.config['violations_reset_days'])).__str__()
            status.add_field(name='Violazioni:', value=str(item['violations_count']) +
                ' (scade il ' + violations_expiration + ')', inline=False)
        await ctx.send(embed=status)

    @commands.command(brief='invia la propic dell\'utente')
    async def avatar(self, ctx, user: discord.User = None):
        """Invia la propria propic o quella dell'utente menzionato. Non è necessario che l'utente
        faccia parte del server, basta che la menzione sia valida.

        Sintassi:
        <avatar             #invia la propria propic
        <avatar @someone    #invia la propic di 'someone'
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

    @commands.command(brief='permette di cambiare nickname periodicamente', hidden=True)
    async def setnick(self, ctx, *, new_nick: str):
        """Permette di cambiare il proprio nickname periodicamente. La frequenza con
        cui è possibile farlo è definita nel config.

        Sintassi:
        <setnick afler       #cambia il nickname in afler
        <setnick due aflers  #può contenere anche più parole
        """
        if BannedWords.contains_banned_words(new_nick):
            await ctx.send('Il nickname non può contenere parole offensive')
            return
        if len(new_nick) > 32:
            await ctx.send('La lunghezza massima del nickname è di 32 caratteri')
            return
        with open('aflers.json', 'r') as file:
            prev_dict = json.load(file)
        try:
            data = prev_dict[str(ctx.author.id)]
        except KeyError:
            await ctx.send('Non tovato nel file :(', delete_after=5)
            return
        last_change = datetime.date(datetime.strptime(data['last_nick_change'], '%Y-%m-%d'))
        difference = datetime.date(datetime.now()) - last_change
        if difference.days >=  Config.config['nick_change_days']:
            data['nick'] = new_nick
            data['last_nick_change'] = datetime.date(datetime.now()).__str__()
            shared_functions.update_json_file(prev_dict, 'aflers.json')
            await ctx.author.edit(nick=new_nick)
            await ctx.send('Nickname cambiato in ' + new_nick)
        else:
            renewal = last_change + timedelta(days=Config.config['nick_change_days'])
            days_until_renewal = renewal - datetime.date(datetime.now())
            await ctx.send('Prossimo cambio tra ' + str(days_until_renewal.days) + ' giorni')

    @commands.command(brief='imposta la propria bio')
    async def setbio(self, ctx, *, bio: str):
        """Permette di impostare una biografia visibile agli altri membri.
        Non sono ovviamente ammesse parole vietate e gli admin si riservano il
        diritto di editare quelle ritenute offensive.

        Sintassi:
        <setbio mia bio    #imposta *mia bio* come bio
        """
        if len(bio) > Config.config['bio_length_limit']:
            await ctx.send('Bio troppo lunga, il limite è ' + str(Config.config['bio_length_limit']) + ' caratteri.')
            return
        if BannedWords.contains_banned_words(bio):
            return
        with open('aflers.json', 'r') as file:
            prev_dict = json.load(file)
        try:
            data = prev_dict[str(ctx.author.id)]
        except KeyError:
            await ctx.send('Non tovato nel file :(', delete_after=5)
            return
        data['bio'] = bio
        shared_functions.update_json_file(prev_dict, 'aflers.json')
        await ctx.send('Bio aggiunta correttamente.')

    @commands.command(brief='ritorna la bio dell\'utente citato')
    async def bio(self, ctx, member: discord.Member = None):
        """Ritorna la propria bio o quella dell'utente citato. Usare
        <setbio per impostare la propria bio

        Sintassi:
        <bio               #ritorna la propria bio
        <bio @someone      #ritorna la bio di *someone*, se presente
        """
        if member is None:
            member = ctx.author
        with open('aflers.json', 'r') as file:
            prev_dict = json.load(file)
        try:
            data = prev_dict[str(member.id)]
        except KeyError:
            await ctx.send('Non tovato nel file :(', delete_after=5)
            return
        if data['bio'] is None:
            await ctx.send('L\'utente selezionato non ha una bio.')
        else:
            bio = discord.Embed(
                title='Bio di ' + member.display_name,
                description=data['bio'],
                color=member.top_role.color
            )
            await ctx.send(embed=bio)


def setup(bot):
    """Entry point per il caricamento della cog"""
    bot.add_cog(UtilityCog(bot))
