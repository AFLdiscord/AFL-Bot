""":class: ConfigCog contiene i comandi di configurazione del bot."""
import git
import json

from discord.ext import commands
from utils import shared_functions
from utils.shared_functions import BannedWords, BotLogger, Config

class ConfigCog(commands.Cog, name='Configurazione'):
    """Contiene i comandi di configurazione del bot:
    - setprefix     cambia il prefisso del bot
    - blackadd      aggiunge una parola bannata all'elenco
    - blackremove   rimuove una parola bannata dall'elenco
    - blacklist     mostra l'elenco delle parole bannate
    - updateconfig  aggiorna la configurazione del bot
    - printconfig   stampa la configurazione corrente
    - pull          git pull dal repository remoto + invoca reload
    - reload        ricarica una o più cogs
    - addcog        aggiunge una o più cog dal bot e dal file extensions.json
    - removecog     rimuove una o più cog dal bot e dal file extensions.json
    - coglist       lista delle estensioni caricate all'avvio
    - addactive     aggiunge un canale all'elenco dei canali conteggiati per l'attivo
    - removeactive  rimuove un canale all'elenco dei canali conteggiati per l'attivo
    - setthresholds permette di gestire le soglie per diversi parametri
    """
    def __init__(self, bot):
        self.bot = bot
        self.logger = BotLogger.get_instance()

    def cog_check(self, ctx):
        """Check sui comandi per autorizzarne l'uso solo ai moderatori."""
        return ctx.author.top_role.id in Config.config['moderation_roles_id']

    @commands.command(brief='aggiunge una parola bannata all\'elenco')
    async def blackadd(self, ctx, *, ban_word):
        """Aggiunge la stringa passata alla lista contenuta e aggiorna banned_words.json.
        Se si scrivono più parole queste vengono considerate come una unica entry.
        Per come sono controllate, non occorre mettere gli spazi tra le parole.
        Esempio:
        <blackadd seistupido   # aggiunge seistupido all'elenco
        il controllo delle parole è poi in grado di capire quali messaggi la contengono
        es. 'sei stupido'  's3i stupid0' vengono tutte rilevate.

        Sintassi:
        <blackadd word           # aggiunge 'word' all'elenco
        <blackadd aListOfWords   # aggiunge 'aListOfWord' come unica entry
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
        <blackremove word     # rimuove 'word' dall'elenco
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
        <blacklist         # stampa la lista
        alias: black, bl
        """
        await ctx.send(BannedWords.to_string())

    @commands.command(brief='cambia il prefisso del bot')
    async def setprefix(self, ctx, prefix):
        """Imposta prefix come nuovo prefisso del bot. Viene memorizzato
        anche nella configurazione del bot e mantenuto in caso di riavvio.

        Sintassi:
        <setprefix ?     # imposta '?' come nuovo prefisso
        """
        self.bot.command_prefix = prefix
        await ctx.send(f'Prefisso cambiato in ``{prefix}``')
        Config.config['current_prefix'] = prefix
        with open('config.json', 'r') as file:
            data = json.load(file)
        data['current_prefix'] = prefix
        shared_functions.update_json_file(data, 'config.json')

    @commands.command(brief='aggiorna la configurazione del bot')
    async def updateconfig(self, ctx):
        """Ricarica la configurazione del bot dal file config.json

        Sintassi:
        <updateconfig     # ricarica tutti i parametri dal file
        """
        if Config.load():
            await ctx.send('Configurazione ricaricata correttamente')
        else:
            await ctx.send('Errore nel caricamento della configurazione, mantengo impostazioni precedenti')

    @commands.command(brief='git pull dal repository remoto')
    async def pull(self, ctx):
        """Pull del codice aggiornato dal repository remoto.
        Effettua due operazioni:
        - git pull
        - invocare reload per aggiornare il bot

        Sintassi:
        <pull         # aggiorna il bot
        """
        repo = git.cmd.Git('.')
        await ctx.send(repo.pull())
        await ctx.invoke(self.bot.get_command('reload'))

    @commands.command(brief='ricarica una o più cogs')
    async def reload(self, ctx, *args):
        """Ricarica le cogs specificate aggiornando le funzionalità. Se nessuna cog è specificata
        le ricarica tutte.

        Sintassi:
        <reload                              # ricarica tutte le estensioni
        <reload moderation_cog               # ricarica solo ModerationCog
        <reload moderation_cog utility_cog   # più cogs separate da spazi
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
                reloaded += '`' + ext + '` '
            except commands.ExtensionError as e:
                print(e)
                await ctx.send('Errore nella ricarica di ' + ext + ' , vedi log del bot.', delete_after=5)
                await ctx.message.delete(delay=5)
        if reloaded != '':
            await ctx.send('Estensioni ' + reloaded + 'ricaricate correttamente.')

    @commands.command(brief='stampa la configurazione corrente')
    async def printconfig(self, ctx):
        """Stampa la configurazione attualmente in uso dal bot.

        Sintassi:
        <printconfig       # stampa la configurazione
        """
        await ctx.send(Config.to_string())

    @commands.command(brief='aggiunge una o più cog dal bot e dal file extensions.json')
    async def addcog(self, ctx, *args):
        """Aggiunge una o più cog al bot e al file extensions.json se non presente in modo
        da caricarla in automatico a ogni futuro riavvio. Occorre passare il nome esatto della
        cog da aggiungere, che deve trovarsi nella cartella cogs del bot.

        Sintassi:
        <addcog nome_cog                # aggiunge nome_cog al bot e al file extensions.json
        <addcog nome_cog altra_cog      # più cogs separate da spazio
        """
        if not args:
            await ctx.send('Devi specificare il nome della cog da caricare.', delete_after=5)
            await ctx.message.delete(delay=5)
        else:
            with open('extensions.json', 'r') as file:
                extensions = json.load(file)
            added = ''
            for ext in args:
                ext = 'cogs.' + ext
                if ext not in extensions:
                    try:
                        self.bot.load_extension(ext)
                    except commands.ExtensionError as e:
                        await ctx.send('Impossibile caricare ' + ext)
                        print(e)
                    else:
                        extensions.append(ext)
                        added += '`' + ext + '` '
                else:
                    await ctx.send(ext + ' già presente.')
            if added != '':
                await ctx.send('Estensioni ' + added + 'aggiunte correttamente.')
            shared_functions.update_json_file(extensions, 'extensions.json')

    @commands.command(brief='rimuove una o più cog dal bot e dal file extensions.json')
    async def removecog(self, ctx, *args):
        """Rimuove una o più cog dal bot e dal file extensions.json se presente così da
        non caricarla più a ogni futuro riavvio del bot. Occorre passare il nome esatto della cog da
        aggiungere, che deve trovarsi nella cartella cogs del bot.

        Sintassi:
        <removecog nome_cog              # rimuove nome_cog dal bot e dal file extensions.json
        <removecog nome_cog altra_cog    # più cogs separate da spazio
        """
        if not args:
            await ctx.send('Devi specificare il nome della cog da rimuovere.', delete_after=5)
            await ctx.message.delete(delay=5)
        else:
            with open('extensions.json', 'r') as file:
                extensions = json.load(file)
            removed = ''
            for ext in args:
                ext = 'cogs.' + ext
                if ext in extensions:
                    extensions.remove(ext)
                try:
                    self.bot.unload_extension(ext)
                except commands.ExtensionError as e:
                    await ctx.send('Impossibile rimuovere ' + ext)
                    print(e)
                else:
                    removed += '`' + ext + '` '
            if removed != '':
                await ctx.send('Estensioni ' + removed + 'rimosse correttamente.')
            shared_functions.update_json_file(extensions, 'extensions.json')

    @commands.command(brief='lista delle estensioni caricate all\'avvio')
    async def coglist(self, ctx):
        """Stampa l'elenco delle estensioni caricate all'avvio del bot prendendole dal file
        extensions.json.

        Sintassi:
        <coglist          # stampa elenco cog
        """
        with open('extensions.json', 'r') as file:
            extensions = json.load(file)
        cogs = ''
        for ext in extensions:
            cogs += '`' + ext + '` '
        await ctx.send('Le estensioni caricate all\'avvio sono:\n' + cogs)

    @commands.command(brief='aggiunge un canale all\'elenco dei canali conteggiati per l\'attivo')
    async def addactive(self, ctx, id: str):
        """Aggiunge il canale all'elenco dei canali conteggiati per l'attivo.
        Occorre attivare le opzioni sviluppatore dal client discord per poter
        copiare gli id dei canali. Se il canale è già presente in lista
        non fa nulla.

        Sintassi:
        <addactive  id_canale    # aggiunge il canale
        """
        # controlla che contenga solo numeri della lunghezza giusta
        if len(id) == 18 and id.isdigit():
            id = int(id)
            if id not in Config.config['active_channels_id']:
                Config.config['active_channels_id'].append(id)
                await ctx.send('Canale <#' + str(id) + '> aggiunto all\'elenco')
                shared_functions.update_json_file(Config.config, 'config.json')
            else:
                await ctx.send('Canale già presente')
        else:
            await ctx.send('Id canale non valido')

    @commands.command(brief='rimuove un canale all\'elenco dei canali conteggiati per l\'attivo')
    async def removeactive(self, ctx, id: str):
        """Rimuove il canale dall'elenco dei canali conteggiati per l'attivo.
        Occorre attivare le opzioni sviluppatore dal client discord per poter
        copiare gli id dei canali. Se il canale non è presente in lista
        non fa nulla.

        Sintassi:
        <removeactive  id_canale    # rimuove il canale
        """
        # controlla che contenga solo numeri della lunghezza giusta
        if len(id) == 18 and id.isdigit():
            id = int(id)
            if id in Config.config['active_channels_id']:
                Config.config['active_channels_id'].remove(id)
                await ctx.send('Canale <#' + str(id) + '> rimosso dall\'elenco')
                shared_functions.update_json_file(Config.config, 'config.json')
            else:
                await ctx.send('Canale non presente in lista')
        else:
            await ctx.send('Id canale non valido')

    @commands.command(brief='permette di gestire le soglie per diversi parametri', aliases=['setthreshold', 'sett', 'threshold'])
    async def setthresholds(self, ctx, category: str, value: str):
        """Permette di gestire le soglie per:
        - messaggi per ruolo attivo
        - durata ruolo attivo
        - cooldown setnick
        - giorni per reset violazioni

        Sintassi:
        <setthreshold attivo 100    # per i giorni dell'attivo
        <setthreshold ruolo 7       # durata ruolo attivo
        <setthreshold setnick 30    # cooldown setnick
        <setthreshold violazioni 7  # reset violazioni

        Ogni comando può essere abbreviato con la prima lettera di ogni soglia.
        es.  '<setthreshold a 100' al posto di '<setthreshold attivo 100'

        alias: setthreshold, sett, threshold
        """
        if not value.isdigit():
            await ctx.send('La soglia deve essere un valore numerico')
            return
        if category.startswith('a'):
            Config.config['active_threshold'] = int(value)
            await ctx.send('Soglia messaggi per l\'attivo cambiata a ' + str(value))
            shared_functions.update_json_file(Config.config, 'config.json')
        elif category.startswith('r'):
            Config.config['active_duration'] = int(value)
            await ctx.send('Durata dell\'attivo cambiata a ' + str(value) + ' giorni')
            shared_functions.update_json_file(Config.config, 'config.json')
        elif category.startswith('s'):
            Config.config['nick_change_days'] = int(value)
            await ctx.send('Cooldown per il setnick cambiata a ' + str(value) + ' giorni')
            shared_functions.update_json_file(Config.config, 'config.json')
        elif category.startswith('v'):
            Config.config['violations_reset_days'] = int(value)
            await ctx.send('Giorni per il reset delle violazioni cambiati a ' + str(value))
            shared_functions.update_json_file(Config.config, 'config.json')
        else:
            await ctx.send('Comando errato, controlla la sintassi')


def setup(bot):
    """Entry point per il caricamento della cog"""
    bot.add_cog(ConfigCog(bot))
