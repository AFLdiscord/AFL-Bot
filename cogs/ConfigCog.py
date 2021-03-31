import json
import discord
from discord.ext import commands
from cogs import sharedFunctions
from cogs.sharedFunctions import BannedWords, Config

"""contiene i comandi di configurazione del bot, in particolare:
- setprefix
- blackadd
- blackremove
- blacklist
"""

class ConfigCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        """check sui comandi per bloccare l'utilizzo dei comandi di moderazione"""
        return ctx.author.top_role.id in Config.config['moderation_roles_id']

    @commands.command()
    async def blackadd(self, ctx, *, ban_word):
        """aggiunge stringhe alla lista contenuta in banned_words.json.
        Se la parola è composta da più parole separate da uno spazio, va messa tra ""
        """
        if ban_word in BannedWords.banned_words:
            await ctx.send(f'la parola è già contenuta nell\'elenco')
            return
        BannedWords.add(ban_word)
        sharedFunctions.update_json_file(BannedWords.banned_words, 'banned_words.json')
        await ctx.send(f'parola aggiunta correttamente', delete_after=5)

    @commands.command()
    async def blackremove(self, ctx, *, ban_word):
        """elimina una banned_word dall'elenco"""
        if ban_word in BannedWords.banned_words:
            BannedWords.remove(ban_word)
            sharedFunctions.update_json_file(BannedWords.banned_words, 'banned_words.json')
            await ctx.send(f'la parola è stata rimossa', delete_after=5)
        else:
            await ctx.send(f'la parola non è presente nell\'elenco', delete_after=5)

    @commands.command(aliases=['black', 'bl'])
    async def blacklist(self, ctx):
        """stampa l'elenco delle parole attualmente bannate"""
        string = ''
        for w in BannedWords.banned_words:
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

    @commands.command()
    async def updateconfig(self, ctx):
        """ricarica la configurazione del bot"""
        if Config.load():
            await ctx.send('Configurazione ricaricata correttamente')
        else:
            await ctx.send('Errore nel caricamento della configurazione, mantengo impostazioni precedenti')
        pass

    @commands.command()
    async def reload(self, ctx, *args):
        """Ricarica le cogs specificate aggiornando le funzionalità. Se nessuna cog è specificata ricarica tutte.
        Sintassi:
        <reload                              #ricarica tutte le estensioni
        <reload ModerationCog                #ricarica solo ModerationCog
        <reload ModerationCog UtilityCog     #più cogs separate da spazi
        """
        if not args:
            cogs = sharedFunctions.get_extensions()
        else:
            cogs = []
            for e in args:
                cogs.append('cogs.' + e)
        reloaded = ''
        for ext in cogs:
            try:
                self.bot.reload_extension(ext)
                reloaded += ext + ' ' 
            except Exception as e:
                print(e)
                await ctx.send('Errore nella ricarica di ' + ext + ' , vedi log del bot.', delete_after=5)
                await ctx.message.delete(delay=5)
        if reloaded.__len__ != 0:
            await ctx.send('Estensioni ' + reloaded + 'ricaricate correttamente.')

def setup(bot):
    bot.add_cog(ConfigCog(bot))