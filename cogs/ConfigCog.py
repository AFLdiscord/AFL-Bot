import json
import discord
from discord.ext import commands
from cogs import sharedFunctions

"""contiene i comandi di configurazione del bot, in particolare:
- setprefix
- blackadd
- blackremove
- blacklist
"""

class ConfigCog(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.MODERATION_ROLES_ID = []
        for mod in config['moderation_roles_id']:
            self.MODERATION_ROLES_ID.append(int(mod))

    async def cog_check(self, ctx):
        """check sui comandi per bloccare l'utilizzo dei comandi di moderazione"""
        return ctx.author.top_role.id in self.MODERATION_ROLES_ID

    @commands.command()
    async def blackadd(self, ctx, *, ban_word):
        """aggiunge stringhe alla lista contenuta in banned_words.json.
        Se la parola è composta da più parole separate da uno spazio, va messa tra ""
        """
        if ban_word in sharedFunctions.BannedWords.banned_words:
            await ctx.send(f'la parola è già contenuta nell\'elenco')
            return
        sharedFunctions.BannedWords.add(ban_word)
        sharedFunctions.update_json_file(sharedFunctions.BannedWords.banned_words, 'banned_words.json')
        await ctx.send(f'parola aggiunta correttamente', delete_after=5)

    @commands.command()
    async def blackremove(self, ctx, *, ban_word):
        """elimina una banned_word dall'elenco"""
        if ban_word in sharedFunctions.BannedWords.banned_words:
            sharedFunctions.BannedWords.remove(ban_word)
            sharedFunctions.update_json_file(sharedFunctions.BannedWords.banned_words, 'banned_words.json')
            await ctx.send(f'la parola è stata rimossa', delete_after=5)
        else:
            await ctx.send(f'la parola non è presente nell\'elenco', delete_after=5)

    @commands.command(aliases=['black', 'bl'])
    async def blacklist(self, ctx):
        """stampa l'elenco delle parole attualmente bannate"""
        string = ''
        for w in sharedFunctions.BannedWords.banned_words:
            string += w + '\n'
        if string == '':
            await ctx.send('Nessuna parola attualmente in elenco')
        else:
            await ctx.send(string)

    @commands.command()
    async def setprefix(self, ctx, prefix):
        """imposta prefix come nuovo prefisso del bot"""
        self.bot.command_prefix = prefix
        await ctx.send(f'Prefisso cambiato in ``{prefix}``')

def setup(bot):
    try:
        with open('config.json', 'r') as file:
            config = json.load(file)
    except FileNotFoundError:
        print('crea il file config.json seguendo le indicazioni del template')
        exit()
    bot.add_cog(ConfigCog(bot, config))