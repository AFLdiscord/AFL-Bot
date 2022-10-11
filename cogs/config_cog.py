""":class: ConfigCog contiene i comandi di configurazione del bot."""
import git
import json
from typing import Any, Dict, List, Optional

from discord.ext import commands
from utils import shared_functions
from utils.shared_functions import Archive, BannedWords, BotLogger, Config


class ConfigCog(commands.Cog, name='Configurazione'):
    """Contiene i comandi di configurazione del bot:
    - setprefix         cambia il prefisso del bot
    - blackadd          aggiunge una parola bannata all'elenco
    - blackremove       rimuove una parola bannata dall'elenco
    - blacklist         mostra l'elenco delle parole bannate
    - updateconfig      aggiorna la configurazione del bot
    - printconfig       stampa la configurazione corrente
    - pull              git pull dal repository remoto + invoca reload
    - reload            ricarica una o più cogs
    - addcog            aggiunge una o più cog dal bot e dal file extensions.json
    - removecog         rimuove una o più cog dal bot e dal file extensions.json
    - coglist           lista delle estensioni caricate all'avvio
    - setthresholds     permette di gestire le soglie per diversi parametri
    - addexception      permette di escludere canali dal controllo parole bannate
    - removeexception   riattiva il controllo delle parole bannate nel canale
    - refresharchive    rilegge l'archivio dal file
    """

    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.logger: BotLogger = BotLogger.get_instance()
        self.config: Config = Config.get_config()

    def cog_check(self, ctx: commands.Context):
        """Check sui comandi per autorizzarne l'uso solo ai moderatori."""
        return ctx.author.top_role.id in self.config.moderation_roles_id

    @commands.command(brief='aggiunge una parola bannata all\'elenco')
    async def blackadd(self, ctx: commands.Context, *, ban_word: str):
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
        shared_functions.update_json_file(
            BannedWords.banned_words, 'banned_words.json')
        await self.logger.log(f'aggiunta parola bannata `{ban_word}`')
        await ctx.send('parola aggiunta correttamente', delete_after=5)

    @commands.command(brief='rimuove una parola bannata dall\'elenco')
    async def blackremove(self, ctx: commands.Context, *, ban_word):
        """Elimina la parola passata dall'elenco delle parole bannate e aggiorna
        il file banned_words.json. Occorre rimuovere la parola scrivendola nello stesso modo
        con cui era stata inserita.

        Sintassi:
        <blackremove word     # rimuove 'word' dall'elenco
        """
        if ban_word in BannedWords.banned_words:
            BannedWords.remove(ban_word)
            shared_functions.update_json_file(
                BannedWords.banned_words, 'banned_words.json')
            await self.logger.log(f'rimossa parola bannata `{ban_word}`')
            await ctx.send('la parola è stata rimossa', delete_after=5)
        else:
            await ctx.send('la parola non è presente nell\'elenco', delete_after=5)

    @commands.command(brief='mostra l\'elenco delle parole bannate', aliases=['black', 'bl'])
    async def blacklist(self, ctx: commands.Context):
        """Stampa l'elenco delle parole attualmente bannate.

        Sintassi:
        <blacklist         # stampa la lista
        alias: black, bl
        """
        await ctx.send(BannedWords.to_string())

    @commands.command(brief='cambia il prefisso del bot')
    async def setprefix(self, ctx: commands.Context, prefix: str):
        """Imposta prefix come nuovo prefisso del bot. Viene memorizzato
        anche nella configurazione del bot e mantenuto in caso di riavvio.

        Sintassi:
        <setprefix ?     # imposta '?' come nuovo prefisso
        """
        self.bot.command_prefix = prefix
        await self.logger.log((f'prefisso cambiato in ``{prefix}``'))
        await ctx.send(f'Prefisso cambiato in ``{prefix}``')
        self.config.current_prefix = prefix
        with open('config.json', 'r') as file:
            data: Dict[str, Any] = json.load(file)
        data['current_prefix'] = prefix
        shared_functions.update_json_file(data, 'config.json')

    @commands.command(brief='aggiorna la configurazione del bot')
    async def updateconfig(self, ctx: commands.Context):
        """Ricarica la configurazione del bot dal file config.json

        Sintassi:
        <updateconfig     # ricarica tutti i parametri dal file
        """
        if Config.load():
            await self.logger.log('aggiornata configurazione')
            await ctx.send('Configurazione ricaricata correttamente')
        else:
            await self.logger.log('errore durante aggiornamento configurazione, mantenute impostazioni precedenti')
            await ctx.send('Errore nel caricamento della configurazione, mantengo impostazioni precedenti')

    @commands.command(brief='git pull dal repository remoto')
    async def pull(self, ctx: commands.Context):
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
        await self.logger.log('aggiornato bot tramite comando pull')

    @commands.command(brief='ricarica una o più cogs')
    async def reload(self, ctx: commands.Context, *args: str):
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
            cogs: List[str] = []
            for e in args:
                cogs.append(f'cogs.{e}')
        reloaded: str = ''
        for ext in cogs:
            try:
                await self.bot.reload_extension(ext)
                reloaded += f'`{ext}` '
            except commands.ExtensionError as e:
                print(e)
                await ctx.send(f'Errore nella ricarica di {ext}, vedi log del bot.', delete_after=5)
                await ctx.message.delete(delay=5)
        if reloaded != '':
            # sync degli slash commands
            await self.bot.tree.sync()
            await self.logger.log(f'estensioni {reloaded} ricaricate correttamente.')
            await ctx.send(f'Estensioni {reloaded} ricaricate correttamente.')

    @commands.command(brief='stampa la configurazione corrente')
    async def printconfig(self, ctx: commands.Context):
        """Stampa la configurazione attualmente in uso dal bot.

        Sintassi:
        <printconfig       # stampa la configurazione
        """
        await ctx.send(str(self.config))

    @commands.command(brief='aggiunge una o più cog dal bot e dal file extensions.json')
    async def addcog(self, ctx: commands.Context, *args: str):
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
            added: str = ''
            for ext in args:
                ext = f'cogs.{ext}'
                if ext not in extensions:
                    try:
                        await self.bot.load_extension(ext)
                    except commands.ExtensionError as e:
                        await ctx.send(f'Impossibile caricare {ext}')
                        print(e)
                    else:
                        extensions.append(ext)
                        added += '`{ext} ` '
                else:
                    await ctx.send(f'{ext} già presente.')
            if added != '':
                await self.logger.log(f'estensioni {added} aggiunte correttamente')
                await ctx.send(f'Estensioni {added} aggiunte correttamente.')
                # sync degli slash commands
                await self.bot.tree.sync()
            shared_functions.update_json_file(extensions, 'extensions.json')

    @commands.command(brief='rimuove una o più cog dal bot e dal file extensions.json')
    async def removecog(self, ctx: commands.Context, *args: str):
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
            removed: str = ''
            for ext in args:
                ext = f'cogs.{ext}'
                if ext in extensions:
                    extensions.remove(ext)
                try:
                    await self.bot.unload_extension(ext)
                except commands.ExtensionError as e:
                    await ctx.send(f'Impossibile rimuovere {ext}')
                    print(e)
                else:
                    removed += '`{ext} ` '
            if removed != '':
                await self.logger.log(f'estensioni {removed} rimosse correttamente')
                await ctx.send(f'Estensioni {removed} rimosse correttamente.')
                # sync degli slash commands
                await self.bot.tree.sync()
            shared_functions.update_json_file(extensions, 'extensions.json')

    @commands.command(brief='lista delle estensioni caricate all\'avvio')
    async def coglist(self, ctx: commands.Context):
        """Stampa l'elenco delle estensioni caricate all'avvio del bot prendendole dal file
        extensions.json.

        Sintassi:
        <coglist          # stampa elenco cog
        """
        with open('extensions.json', 'r') as file:
            extensions: List[str] = json.load(file)
        cogs: str = ''
        for ext in extensions:
            cogs += f'`{ext} ` '
        await ctx.send(f'Le estensioni caricate all\'avvio sono:\n{cogs}')

    @commands.command(brief='permette di gestire le soglie per diversi parametri', aliases=['setthreshold', 'sett', 'threshold'])
    async def setthresholds(self, ctx: commands.Context, category: str, value: str):
        """Permette di gestire le soglie per:
        - ruoli oratore e cazzaro
        - cooldown setnick
        - giorni per reset violazioni

        Sintassi: <setthreshold [parametro] [valore]

        parametro | v.default | unità | descrizione
        ------------------------------------------------------------
        oratore     100         msg     oratore
        d-oratore   7           giorni  durata oratore
        cazzaro     100         msg     cazzaro
        d-cazzaro   7           giorni  durata cazzaro
        tw-cazzaro  7           giorni  finestra di tempo cazzaro
        setnick     30          giorni  cooldown setnick
        violazioni  7           giorni  reset violazioni

        Ogni comando può essere abbreviato con la prima lettera di ogni soglia.
        E.g.  '<setthreshold o 100' al posto di '<setthreshold oratore 100'

        alias: setthreshold, sett, threshold

        :param category: il parametro di cui si vuole modificare la soglia
        :param value: il nuovo valore da impostare per la soglia
        """
        if not value.isdigit():
            await ctx.send('La soglia deve essere un valore numerico')
            return
        msg: str = ''
        if category.startswith('o'):
            self.config.orator_threshold = int(value)
            msg = f'Soglia messaggi per l\'oratore cambiata a {value}'
        elif category.startswith('d-o'):
            self.config.orator_duration = int(value)
            msg = f'Durata dell\'oratore cambiata a {value}  giorni'
        elif category.startswith('c'):
            self.config.dank_threshold = int(value)
            msg = f'Soglia messaggi per il cazzaro cambiata a {value}'
        elif category.startswith('d-c'):
            self.config.dank_duration = int(value)
            msg = f'Durata del cazzaro cambiata a {value}  giorni'
        elif category.startswith('tw-c'):
            self.config.dank_duration = int(value)
            msg = f'Finestra di tempo del cazzaro cambiata a {value}  giorni'
        elif category.startswith('s'):
            self.config.nick_change_days = int(value)
            msg = f'Cooldown per il setnick cambiata a {value} giorni'
        elif category.startswith('v'):
            self.config.violations_reset_days = int(value)
            msg = f'Giorni per il reset delle violazioni cambiati a {value}'
        else:
            await ctx.send('Comando errato, controlla la sintassi')
            return
        await self.logger.log(msg)
        await ctx.send(msg)
        self.config.save()

    @commands.command(brief='permette di escludere canali dal controllo parole bannate', aliases=['addex'])
    async def addexception(self, ctx: commands.Context, id: str):
        """Aggiunge il canale all'elenco dei canali esclusi dal controllo sulle parole
        bannate. Può essere usato con id del canale o menzione.

        Sintassi:
        <addexception id      # aggiunge il canale con id
        <addexception #canale # aggiunge il canale con menzione

        alias: addex
        """
        # strip dei caratteri per la menzione
        id = id.strip('<#>')
        # controlla che contenga solo numeri della lunghezza giusta
        if len(id) in (18, 19) and id.isdigit():
            int_id = int(id)
        else:
            await ctx.send('Id canale non valido')
            return
        if int_id not in self.config.exceptional_channels_id:
            self.config.exceptional_channels_id.append(int_id)
            await self.logger.log('canale <#' + id + '> aggiunto ai canali esclusi')
            await ctx.send('Canale <#' + id + '> aggiunto ai canali esclusi')
            self.config.save()
        else:
            await ctx.send('Canale già presente')

    @commands.command(brief='riattiva il controllo delle parole bannate nel canale', aliases=['remex'])
    async def removeexception(self, ctx: commands.Context, id: str):
        """Rimuove il canale all'elenco dei canali esclusi dal controllo sulle parole
        bannate. Può essere usato con id del canale o menzione.

        Sintassi:
        <removeexception id      # rimuove il canale con id
        <removeexception #canale # rimuove il canale con menzione

        alias: remex
        """
        # strip dei caratteri della menzione
        id = id.strip('<#>')
        # controlla che contenga solo numeri della lunghezza giusta
        if len(id) in (18, 19) and id.isdigit():
            int_id = int(id)
        else:
            await ctx.send('Id canale non valido')
            return
        if int_id in self.config.exceptional_channels_id:
            self.config.exceptional_channels_id.remove(int_id)
            await self.logger.log('canale <#' + id + '> rimosso dai canali esclusi')
            await ctx.send('Canale <#' + id + '> rimosso dai canali esclusi')
            self.config.save()
        else:
            await ctx.send('Canale non presente in lista')

    @commands.command(brief='permette di refreshare l\'archivio', aliases=['refresh'])
    async def refresharchive(self, ctx: commands.Context) -> None:
        """Aggiorna l'archivio del bot, rileggendolo dal disco.
        Utile quando si interviene manualmente sul file.
        Prima di ricaricare i dati salva una copia dell'archivio corrente
        in 'afler.json.old'.
        """
        Archive.refresh()
        await ctx.send('Archivio ricaricato correttamente')
        await self.logger.log('Archivio ricaricato correttamente')


async def setup(bot: commands.Bot):
    """Entry point per il caricamento della cog"""
    await bot.add_cog(ConfigCog(bot))
