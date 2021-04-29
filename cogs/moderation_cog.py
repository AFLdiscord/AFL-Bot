""":class: ModerationCog contiene tutti i comandi per la moderazione."""
import json
from datetime import datetime

import discord
from discord.ext import commands
from utils import shared_functions
from utils.shared_functions import BannedWords, Config

class ModerationCog(commands.Cog, name='Moderazione'):
    """Contiene i comandi relativi alla moderazione:
    - warn       aggiunge un warn all'utente citato
    - unwarn     rimuove un warn all'utente citato
    - ban        banna l'utente citato
    - warncount  mostra i warn di tutti i membri
    Inoltre effettua il controllo sul contenuto dei messaggi e elimina quelli dal contenuto inadatto.
    Questi comandi possono essere usati solo da coloro che possiedono un ruolo di moderazione.
    """
    def __init__(self, bot):
        self.bot = bot

    def cog_check(self, ctx):
        """Check sui comandi per autorizzarne l'uso solo ai moderatori."""
        return ctx.author.top_role.id in Config.config['moderation_roles_id']

    @commands.Cog.listener()
    async def on_message(self, message):
        """Elimina i messaggi inappropriati dai canali e aggiunge un warn all'utente.
        Ignora i messaggi da:
        - il bot stesso
        - altri bot
        - canali di chat privata
        - canali ignorati (vedi config.template)
        """
        if message.author == self.bot.user or message.author.bot or message.guild is None:
            return
        if BannedWords.contains_banned_words(message.content) and message.channel.id not in Config.config['exceptional_channels_id']:
            await message.delete()
            await self._add_warn(message.author, 'linguaggio inappropriato', 1)

    @commands.command(brief='aggiunge un warn all\'utente citato')
    async def warn(self, ctx, attempted_member=None, *, reason='un moderatore ha ritenuto inopportuno il tuo comportamento'):
        """Aggiunge un warn all'utente menzionato nel messaggio. Si può menzionare in diversi modi.
        L'effetto è il seguente:
        - aggiunge un warn all'autore del messaggio a cui si risponde/utente menzionato
        - cancella il messaggio citato (se presente)
        - cancella il comando di warn

        Sintassi:
        <warn @someone         #warn all'utente menzionato 'someone'
        <warn @someone reason  #aggiunge una ragione specifica al warn, se non specificata
                               #reason='un moderatore ha ritenuto inopportuno il tuo comportamento'

        è possibile usarlo anche direttamente in risposta al messaggio oggetto del warn lasciando
        attiva la menzione (clic destro sul messaggio -> rispondi). In tal caso

          @someone messaggio citato
        <warn                          #aggiunge warn a 'someone'
          @someone messaggio citato
        <warn reason                   #aggiunge warn a 'someone' con ragione 'reason'
        """
        if attempted_member is None:   #nessun argomento passato al warn
            if ctx.message.reference is None:
                #sono in questo caso quando mando <warn da solo
                await ctx.send("Devi menzionare qualcuno o rispondere a un messaggio per poter usare questo comando", delete_after=5)
                return
            #in questo caso ho risposto a un messaggio con <warn
            msg = await ctx.fetch_message(ctx.message.reference.message_id)
            member = msg.author
            await msg.delete()
        else:   #con argomenti al warn
            if not ctx.message.mentions:   #nessuna menzione nel messaggio
                await ctx.send("Devi menzionare qualcuno o rispondere a un messaggio per poter usare questo comando", delete_after=5)
                return
            if ctx.message.reference is None:
                #ho chiamato il warn a mano <warn @somebody ragione
                member = ctx.message.mentions[0]
            else:
                #ho menzionato qualcuno, prendo come target del warn
                msg = await ctx.fetch_message(ctx.message.reference.message_id)
                member = msg.author
                await msg.delete()
                #solo se vado per reference devo sistemare la reason perchè la prima parola va in attempted_member
                if reason == 'un moderatore ha ritenuto inopportuno il tuo comportamento':
                    reason = attempted_member   #ragione di una sola parola, altrimenti poi concatena tutto
                else:
                    reason = attempted_member + ' ' + reason  #devo inserire uno spazio altrimenti scrive tutto appicciato
        if member.bot:   # or member == ctx.author:
            return
        await self._add_warn(member, reason, 1)
        user = '<@!' + str(member.id) + '>'
        await ctx.send(user + ' warnato. Motivo: ' + reason)
        await ctx.message.delete(delay=5)

    @commands.command(brief='rimuove un warn all\'utente citato')
    async def unwarn(self, ctx, member: discord.Member):
        """Rimuove un warn all'utente menzionato. Se non aveva warn non fa nulla.

        Sintassi:
        <unwarn @someone      #rimuove un warn a 'someone'
        """
        if member.bot:
            return
        reason = 'buona condotta'
        await self._add_warn(member, reason, -1)
        user = '<@!' + str(member.id) + '>'
        await ctx.send(user + ' rimosso un warn.')
        await ctx.message.delete(delay=5)

    @commands.command(brief='mostra i warn di tutti i membri', aliases=['warnc', 'wc'])
    async def warncount(self, ctx):
        """Stampa nel canale in cui viene chiamato l'elenco di tutti i warn degli utenti.
        Esempio output:
        membro1: 1 warn
        membro2: 3 warn

        Sintassi:
        <warncount
        alias: warnc, wc
        """
        try:
            with open('aflers.json','r') as file:
                prev_dict = json.load(file)
        except FileNotFoundError:
            await ctx.send('nessuna attività registrata', delete_after=5)
            await ctx.message.delete(delay=5)
            return
        warnc = ''
        for user in prev_dict:
            name = self.bot.get_guild(Config.config['guild_id']).get_member(int(user)).display_name
            item = prev_dict[user]
            count = str(item["violations_count"])
            msg = name + ': ' + count + ' warn\n'
            warnc += msg
        await ctx.send(warnc)

    @commands.command(brief='banna il membro citato')
    async def ban(self, ctx, member: discord.Member = None, *, reason='un moderatore ha ritenuto inopportuno il tuo comportamento'):
        """Banna un membro dal server.

        Sintassi:
        <ban @someone     #banna 'someone'
        """
        if member is None:
            await ctx.send('specifica un membro da bannare', delete_after=5)
            await ctx.message.delete(delay=5)
            return
        user = '<@!' + str(member.id) + '>'
        await ctx.send(user + ' bannato. Motivo: ' + reason)
        await ctx.message.delete(delay=5)
        penalty = 'bannato dal server.'
        channel = await member.create_dm()
        await channel.send('Sei stato ' + penalty + ' Motivo: ' + reason + '.')
        await member.ban(delete_message_days = 0, reason = reason)

    async def _add_warn(self, member: discord.Member, reason: str, number: int):
        """Incrementa o decremente il numero di violazioni di numero e tiene traccia
        dell'ultima violazione commessa. Si occupa anche di inviare in dm la notifica
        dell'avvenuta violazione con la ragione che è stata specificata.
        """
        prev_dict = {}
        penalty = 'warnato.'
        try:
            with open('aflers.json','r') as file:
                prev_dict = json.load(file)
        except FileNotFoundError:
            print('file non trovato, lo creo ora')
            with open('aflers.json','w+') as file:
                prev_dict = {}
        key = str(member.id)
        if key in prev_dict:
            data = prev_dict[key]
            data["violations_count"] += number
            data["last_violation_count"] = datetime.date(datetime.now()).__str__()
            shared_functions.update_json_file(prev_dict, 'aflers.json')
            if data["violations_count"] <= 0:
                data["violations_count"] = 0
                data["last_violation_count"] = None
                shared_functions.update_json_file(prev_dict, 'aflers.json')
                return
            if number < 0:  #non deve controllare se è un unwarn
                return
            if data["violations_count"] == 3:
                await member.add_roles(self.bot.get_guild(Config.config['guild_id']).get_role(Config.config['under_surveillance_id']))
                penalty = 'sottoposto a sorveglianza, il prossimo sara\' un ban.'
                channel = await member.create_dm()
                shared_functions.update_json_file(prev_dict, 'aflers.json')
                await channel.send('Sei stato ' + penalty + ' Motivo: ' + reason + '.')
            elif data["violations_count"] >= 4:
                penalty = 'bannato dal server.'
                channel = await member.create_dm()
                await channel.send('Sei stato ' + penalty + ' Motivo: ' + reason + '.')
                shared_functions.update_json_file(prev_dict, 'aflers.json')
                await member.ban(delete_message_days = 0, reason = reason)
            else:
                channel = await member.create_dm()
                shared_functions.update_json_file(prev_dict, 'aflers.json')
                await channel.send('Sei stato ' + penalty + ' Motivo: ' + reason + '.')
        else:
            #contatore per ogni giorno per ovviare i problemi discussi nella issue #2
            if number < 0:
                return
            afler = {
                "nick": member.display_name,
                "last_nick_change": datetime.date(datetime.now()).__str__(),
                "mon": 0,
                "tue": 0,
                "wed": 0,
                "thu": 0,
                "fri": 0,
                "sat": 0,
                "sun": 0,
                "counter": 0,
                "last_message_date": None,
                "violations_count": number,
                "last_violation_count": datetime.date(datetime.now()).__str__(),
                "active": False,
                "expiration": None
            }
            prev_dict[key] = afler
            shared_functions.update_json_file(prev_dict, 'aflers.json')

def setup(bot):
    """Entry point per il caricamento della cog"""
    bot.add_cog(ModerationCog(bot))
