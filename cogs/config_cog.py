""":class: ConfigCog contiene i comandi di configurazione del bot."""
from discord.ext import commands
from cogs import shared_functions
from cogs.shared_functions import BannedWords, Config

class ConfigCog(commands.Cog, name='Configurazione'):
    """Contiene i comandi di configurazione del bot:
    - setprefix     cambia il prefisso del bot
    - blackadd      aggiunge una parola bannata all'elenco
    - blackremove   rimuove una parola bannata dall'elenco
    - blacklist     mostra l'elenco delle parole bannate
    - updateconfig  aggiorna la configurazione del bot
    - reload        ricarica una o più cogs
    """
    def __init__(self, bot):
        self.bot = bot

    def cog_check(self, ctx):
        """Check sui comandi per autorizzarne l'uso solo ai moderatori."""
        return ctx.author.top_role.id in Config.config['moderation_roles_id']

    @commands.command(brief='aggiunge una parola bannata all\'elenco')
    async def blackadd(self, ctx, *, ban_word):
        """Aggiunge la stringa passata alla lista contenuta e aggiorna banned_words.json.
        Se si scrivono più parole queste vengono considerate come una unica entry.
        Per come sono controllate, non occorre mettere gli spazi tra le parole.
        Esempio:
        <blackadd seistupido   #aggiunge seistupido all'elenco
        il controllo delle parole è poi in grado di capire quali messaggi la contengono
        es. "sei stupido"  "s3i stupid0" vengono tutte rilevate.

        Sintassi:
        <blackadd word           #aggiunge 'word' all'elenco
        <blackadd aListOfWords   #aggiunge 'aListOfWord' come unica entry
        """
        if ban_word in BannedWords.banned_words:
            await ctx.send('la parola è già contenuta nell\'elenco')
            return
        BannedWords.add(ban_word)
        shared_functions.update_json_file(BannedWords.banned_words, 'banned_words.json')
        await ctx.send('parola aggiunta correttamente', delete_after=5)

    @commands.command(brief='rimuove una parola bannata dall\'elenco')
    async def blackremove(self, ctx, *, ban_word):
        """Elimina la parola passata dall'elenco delle parole bannate e aggiorna
        il file banned_words.json. Occorre rimuovere la parola scrivendola nello stesso modo
        con cui era stata inserita.

        Sintassi:
        <blackremove word     #rimuove 'word' dall'elenco
        """
        if ban_word in BannedWords.banned_words:
            BannedWords.remove(ban_word)
            shared_functions.update_json_file(BannedWords.banned_words, 'banned_words.json')
            await ctx.send('la parola è stata rimossa', delete_after=5)
        else:
            await ctx.send('la parola non è presente nell\'elenco', delete_after=5)

    @commands.command(brief='mostra l\'elenco delle parole bannate', aliases=['black', 'bl'])
    async def blacklist(self, ctx):
        """Stampa l'elenco delle parole attualmente bannate.

        Sintassi:
        <blacklist         #stampa la lista
        alias: black, bl
        """
        string = ''
        for w in BannedWords.banned_words:
            string += w + '\n'
        if string == '':
            await ctx.send('Nessuna parola attualmente in elenco')
        else:
            await ctx.send(string)

    @commands.command(brief='cambia il prefisso del bot')
    async def setprefix(self, ctx, prefix):
        """Imposta prefix come nuovo prefisso del bot. Se si vuole
        cambiare il prefisso permanentemente aggiornare il file di configurazione
        config.json e ricaricare i parametri col comando apposito
        
        Sintassi:
        <setprefix ?     #imposta '?' come nuovo prefisso
        """
        self.bot.command_prefix = prefix
        await ctx.send(f'Prefisso cambiato in ``{prefix}``')

    @commands.command(brief='aggiorna la configurazione del bot')
    async def updateconfig(self, ctx):
        """Ricarica la configurazione del bot dal file config.json
        
        Sintassi:
        <updateconfig     #ricarica tutti i parametri dal file
        """
        if Config.load():
            await ctx.send('Configurazione ricaricata correttamente')
        else:
            await ctx.send('Errore nel caricamento della configurazione, mantengo impostazioni precedenti')

    @commands.command(brief='ricarica una o più cogs')
    async def reload(self, ctx, *args):
        """Ricarica le cogs specificate aggiornando le funzionalità. Se nessuna cog è specificata
        le ricarica tutte.

        Sintassi:
        <reload                              #ricarica tutte le estensioni
        <reload moderation_cog               #ricarica solo ModerationCog
        <reload moderation_cog utility_cog   #più cogs separate da spazi
        """
        if not args:
            cogs = shared_functions.get_extensions()
        else:
            cogs = []
            for e in args:
                cogs.append('cogs.' + e)
        reloaded = ''
        for ext in cogs:
            try:
                self.bot.reload_extension(ext)
                reloaded += ext + ' '
            except commands.ExtensionError as e:
                print(e)
                await ctx.send('Errore nella ricarica di ' + ext + ' , vedi log del bot.', delete_after=5)
                await ctx.message.delete(delay=5)
        if reloaded.__len__ != 0:
            await ctx.send('Estensioni ' + reloaded + 'ricaricate correttamente.')

def setup(bot):
    """Entry point per il caricamento della cog"""
    bot.add_cog(ConfigCog(bot))
