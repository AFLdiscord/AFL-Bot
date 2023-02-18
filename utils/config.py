from __future__ import annotations
import json
from typing import ClassVar, List, TypedDict

from aflbot import AFLBot
from utils import shared_functions

import discord
from discord.utils import MISSING


class ConfigFields(TypedDict):
    """Helper per definire la struttura del file di config"""
    guild_id: int
    main_channel_id: int
    presentation_channel_id: int
    welcome_channel_id: int
    log_channel_id: int
    current_prefix: str
    moderation_roles_id: list[int]
    afl_role_id: int
    orator_role_id: int
    orator_category_id: int
    orator_threshold: int
    orator_duration: int
    dank_role_id: int
    dank_category_id: int
    dank_threshold: int
    dank_time_window: int
    dank_duration: int
    exceptional_channels_id: list[int]
    poll_channel_id: int
    poll_duration: int
    under_surveillance_id: int
    violations_reset_days: int
    nick_change_days: int
    bio_length_limit: int
    greetings: str


TextChannelsList = type(List[discord.TextChannel])
RolesList = type(List[discord.Role])


class Model(TypedDict):
    """Modelli da caricare a partire dagli id definiti sopra"""
    guild: discord.Guild
    main_channel: discord.TextChannel
    presentation_channel: discord.TextChannel
    welcome_channel: discord.TextChannel
    log_channel: discord.TextChannel
    exceptional_channels: TextChannelsList
    poll_channel: discord.TextChannel
    moderation_roles: RolesList
    afl_role: discord.Role
    orator_role: discord.Role
    orator_category: discord.CategoryChannel
    dank_role: discord.Role
    dank_category: discord.CategoryChannel
    surveillance_role: discord.Role


class Config():
    """Gestione dei parametri di configurazione del bot. Salva tutti i parametri in un dizionario
    che può essere usato dal resto del bot per svolgere la sua funzione. I parametri possono essere
    aggiornati in ogni momento ricaricando i valori dal file config.json che si aspetta di trovare
    nella cartella del bot. Non è fornito un metodo __init__ poichè questa classe è pensata solo per
    utilizzare metodi e attributi statici.

    Attributes
    -------------
    guild_id: `int`                   id del server in cui contare i messaggi
    main_channel_id: `int`            canale dei messaggi di sistema del bot
    presentation_channel_id: `int`    canale in cui i nuovi membri si presentano prima dell'ammissione
    welcome_channel_id: `int`         canale di benvenuto in cui si annunciano i nuovi membri
    log_channel_id: `int`             canale del server in cui si ricevono i messaggi di log del bot
    current_prefix: `int`             prefisso per i comandi del bot
    moderation_roles_id: `int`        [id dei ruoli di moderazione separati da virgola se più di uno]
    afl_role_id: `int`                id del ruolo AFL
    orator_role_id: `int`             id del ruolo oratore
    orator_category_id: `int`         id della categoria dei canali rilevanti al conteggio oratore
    orator_threshold: `int`           numero di messaggi da mandare prima di ricevere il ruolo oratore
    orator_duration: `int`            durata del ruolo oratore in GIORNI
    dank_role_id: `int`               id del ruolo cazzari
    dank_category_id: `int`           id della categoria dei canali rilevanti al conteggio cazzaro
    dank_threshold: `int`             numero di messaggi da mandare prima di ricevere il ruolo cazzaro
    dank_time_window: `int`           giorni a disposizione per mandare i messaggi per il ruolo cazzaro
    dank_duration: `int`              durata del ruolo cazzaro in GIORNI
    exceptional_channels_id: `int`    [elenco dei canali non controllati dal bot, separati da virgola se più di uno]
    poll_channel_id: `int`            canale in cui controllare le reaction alle proposte
    poll_duration: `int`              empo di voto per le proposte in giorni
    under_surveillance_id: `int`      id del ruolo sotto sorveglianza (vedi regole)
    violations_reset_days: `int`      tempo dopo cui si resettano le violazioni in giorni
    nick_change_days: `int`           giorni concessi tra un cambio di nickname e l'altro (0 nessun limite)
    bio_length_limit: `int`           massimo numero di caratteri per la bio
    greetings: `str`                  messaggio di benvenuto per i nuovi membri

    Methods
    -------------
    load():  carica i valori dal file config.json
    """
    _instance: ClassVar[Config] = MISSING
    _bot: AFLBot = MISSING

    def __init__(self) -> None:
        raise RuntimeError(
            'Usa Config.get_config() per ottenere la configurazione')

    def __str__(self) -> str:
        """Rappresentazione della configurazione del bot come stringa.

        :returns: la configurazione corrente del bot
        :rtype: str
        """
        attributes = vars(self)
        fields = ConfigFields.__annotations__.keys()
        string = ''
        for key in fields:
            string += f'{key} = {attributes[key]}\n'
        return string

    @classmethod
    def set_bot(cls, bot: AFLBot):
        cls._bot = bot

    @classmethod
    def get_config(cls):
        if cls._instance is MISSING:
            cls._instance = cls.__new__(cls)
            cls._instance.load()
        return cls._instance

    def load(self) -> bool:
        """Carica i parametri dal file config.json nell'attributo di classe config. Il formato del
        file deve essere quello specificato nel template (vedi config.template). Deve essere
        chiamato all'avvio del bot. Ritorna un booleano con l'esito.
        In caso di fallimento mantiene inalterato il config attuale.

        :returns: vero o falso a seconda dell'esito
        :rtype: bool
        """
        try:
            with open('config.json', 'r') as file:
                data = json.load(file)
                self._load_config(data)
                if Config._bot is not MISSING:
                    self.load_models()
                print('configurazione ricaricata correttamente')
                return True
        except (FileNotFoundError, json.decoder.JSONDecodeError, AssertionError) as e:
            print(e)
            print(
                'errore nella ricarica della configurazione, mantengo configurazione precedente')
            return False

    def _load_config(self, data: ConfigFields) -> None:
        """Converte i valori letti dal dizionario nei tipi corretti. Chiamato dalla load, non
        utilizzare direttamente questo metodo.
        """
        self.guild_id = int(data['guild_id'])
        self.main_channel_id = int(data['main_channel_id'])
        self.presentation_channel_id = int(data['presentation_channel_id'])
        self.welcome_channel_id = int(data['welcome_channel_id'])
        self.log_channel_id = int(data['log_channel_id'])
        self.current_prefix = data['current_prefix']
        self.moderation_roles_id = []
        for mod in data['moderation_roles_id']:
            self.moderation_roles_id.append(int(mod))
        self.afl_role_id = int(data['afl_role_id'])
        self.orator_role_id = int(data['orator_role_id'])
        self.orator_category_id = int(data['orator_category_id'])
        self.orator_threshold = data['orator_threshold']
        self.orator_duration = data['orator_duration']
        self.dank_role_id = int(data['dank_role_id'])
        self.dank_category_id = int(data['dank_category_id'])
        self.dank_threshold = data['dank_threshold']
        self.dank_time_window = data['dank_time_window']
        self.dank_duration = data['dank_duration']
        self.exceptional_channels_id = []
        for channel in data['exceptional_channels_id']:
            self.exceptional_channels_id.append(int(channel))
        self.poll_channel_id = int(data['poll_channel_id'])
        self.poll_duration = int(data['poll_duration'])
        self.under_surveillance_id = int(data['under_surveillance_id'])
        self.violations_reset_days = data['violations_reset_days']
        self.nick_change_days = data['nick_change_days']
        self.bio_length_limit = data['bio_length_limit']
        self.greetings = data['greetings']

    def load_models(self):
        """Carica i modelli il cui id è riportato nel file di configurazione.
        In caso di errore (un id errato) dovrebbe riportare il parametro
        errato nella configurazione.
        """
        _guild = self._bot.get_guild(self.guild_id)
        assert isinstance(_guild, discord.Guild), 'Id guild non corretto'
        self.guild = _guild
        _main_channel = self._bot.get_channel(self.main_channel_id)
        _presentation_channel = self._bot.get_channel(
            self.presentation_channel_id)
        _welcome_channel = self._bot.get_channel(self.welcome_channel_id)
        _log_channel = self._bot.get_channel(self.log_channel_id)
        _exceptional_channels = [self._bot.get_channel(
            c) for c in self.exceptional_channels_id]
        _poll_channel = self._bot.get_channel(self.poll_channel_id)
        _moderation_roles = [self.guild.get_role(
            r) for r in self.moderation_roles_id]
        _afl_role = self.guild.get_role(self.afl_role_id)
        _orator_role = self.guild.get_role(self.orator_role_id)
        _orator_category = self._bot.get_channel(self.orator_category_id)
        _dank_role = self.guild.get_role(self.dank_role_id)
        _dank_category = self._bot.get_channel(self.dank_category_id)
        _surveillance_role = self.guild.get_role(
            self.under_surveillance_id)
        assert isinstance(
            _main_channel, discord.TextChannel), 'Id main_channel non corretto'
        assert isinstance(
            _presentation_channel, discord.TextChannel), 'Id presentation_channel non corretto'
        assert isinstance(
            _welcome_channel, discord.TextChannel), 'Id welcome_channel non corretto'
        assert isinstance(
            _log_channel, discord.TextChannel), 'Id log_channel non corretto'
        for channel in _exceptional_channels:
            assert isinstance(
                channel, discord.TextChannel), 'Id di un exceptional_channel non corretto'
        assert isinstance(
            _poll_channel, discord.TextChannel), 'Id poll_channel non corretto'
        for role in _moderation_roles:
            assert isinstance(
                role, discord.Role), 'Id di un moderation_role non corretto'
        assert isinstance(_afl_role, discord.Role), 'Id afl_role non corretto'
        assert isinstance(
            _orator_role, discord.Role), 'Id orator_role non corretto'
        assert isinstance(
            _orator_category, discord.CategoryChannel), 'Id orator_category non corretto'
        assert isinstance(
            _dank_role, discord.Role), 'Id dank_role non corretto'
        assert isinstance(
            _dank_category, discord.CategoryChannel), 'Id dank_category non corretto'
        assert isinstance(_surveillance_role,
                          discord.Role), 'Id surveillance_role non corretto'
        self.main_channel = _main_channel
        self.presentation_channel = _presentation_channel
        self.welcome_channel = _welcome_channel
        self.log_channel = _log_channel
        self.exceptional_channels = _exceptional_channels
        self.poll_channel = _poll_channel
        self.moderation_roles = _moderation_roles
        self.afl_role = _afl_role
        self.orator_role = _orator_role
        self.orator_category = _orator_category
        self.dank_role = _dank_role
        self.dank_category = _dank_category
        self.surveillance_role = _surveillance_role

    def save(self) -> None:
        """Save the current config"""
        shared_functions.update_json_file(vars(self), 'config.json')
