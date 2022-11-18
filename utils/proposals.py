"""Modulo di gestione delle proposte"""

from __future__ import annotations
from datetime import date, timedelta
import json
from typing import ClassVar, Dict, Optional, TypedDict

import discord
from discord.utils import MISSING
from utils import shared_functions as sf
from utils.config import Config
from utils.bot_logger import BotLogger


class Proposal():
    """Wrapper per le singole proposte.

    Attributes
    -------------
    timestamp: `str`    la data della proposta

    total_voters: `int` la quantità totale di persone che devono votare
    al momento della proposta

    threshold: `int`    la quantità minima di voti che deve ricevere una
    proposta per considerarsi valida (passata o bocciata)

    passed: `bool`      parametro messo a True se la proposta è passata

    rejected: `bool`    parametro messo a True se la proposta è stata
    bocciata

    yes: `int`          numero di voti a favore

    no: `int`           numero di voti contrari

    content: `str`      contenuto della proposta

    Methods
    -------------
    adjust_vote_count():    aggiorna i voti di una proposta
    """

    def __init__(
            self,
            timestamp: str,
            total_voters: int,
            threshold: int,
            content: str,
            passed: bool = False,
            rejected: bool = False,
            yes: int = 0,
            no: int = 0) -> None:
        self.timestamp: str = timestamp
        self.total_voters: int = total_voters
        self.threshold: int = threshold
        self.passed: bool = passed
        self.rejected: bool = rejected
        self.yes: int = yes
        self.no: int = no
        self.content: str = content

    def adjust_vote_count(self, vote: str, change: int) -> None:
        """Aggiusta il contatore dei voti in base al parametro passato.
        Stabilisce in autonomia se il voto è a favore o contrario guardando
        il tipo di emoji cambiata.

        :param payload: l'evento di rimozione dell'emoji
        :param change: variazione del voto (+1 o -1)
        """
        if vote == '🟢':
            self.yes += change
            if self.yes < 0:
                self.yes = 0
            if self.yes >= self.threshold:
                self.passed = True
            else:
                # è possibile cambiare idea, in quel caso deve
                self.passed = False
        else:
            # se vote == '🔴'
            self.no += change
            if self.no < 0:
                self.no = 0
            if self.no >= self.threshold:
                self.rejected = True
            else:
                self.rejected = False


class ProposalType(TypedDict):
    """Utility per parsare l'archivio delle proposte durante la load()"""
    timestamp: str
    total_voters: int
    threshold: int
    content: str
    passed: bool
    rejected: bool
    yes: int
    no: int


class Proposals():
    """Wrapper per l'archivio delle proposte.

    Contiene tutte le operazioni necessarie per gestire le proposte.

    Attributes
    -------------
    _instance: `ClassVar[Proposals]`    attributo di classe, contiene
    l'istanza del wrapper

    Classmethods
    -------------
    load():         carica il contenuto del file nell'attributo di classe

    get_instance(): ritorna l'unica istanza del wrapper

    Methods
    -------------
    get_proposal():         ritorna la proposta richiesta

    add_proposal():         aggiunge una nuova proposta all'archivio

    remove_proposal():      rimuove la proposta dall'archivio

    adjust_vote_count():    aggiorna i voti di una proposta

    handle_proposals():     controlla lo stato delle proposte
    """
    _instance: ClassVar[Proposals] = MISSING

    def __init__(self) -> None:
        self.proposals: Dict[int, Proposal]
        raise RuntimeError(
            'Usa Proposals.get_instance() per ottenere l\'istanza')

    @classmethod
    def get_instance(cls):
        """Restituisce l'unica istanza di questa classe."""
        if cls._instance is MISSING:
            cls.load()
        return cls._instance

    @classmethod
    def load(cls) -> None:
        """Legge le proposte da file."""
        raw_proposals: Dict[str, ProposalType]
        try:
            with open('proposals.json', 'r') as file:
                raw_proposals = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            if isinstance(e, FileNotFoundError):
                mode = 'x'
            else:
                mode = 'w'
            raw_proposals = {}
            with open('proposals.json', mode) as file:
                file.write('{}')
        proposals = {int(i): Proposal(
            timestamp=p['timestamp'],
            total_voters=p['total_voters'],
            threshold=p['threshold'],
            passed=p['passed'],
            rejected=p['rejected'],
            yes=p['yes'],
            no=p['no'],
            content=p['content']
        ) for i, p in raw_proposals.items()}
        cls._instance = cls.__new__(cls)
        cls._instance.proposals = proposals

    def get_proposal(self, messsage_id: int) -> Optional[Proposal]:
        """Cerca una proposta dato l'id del messaggio ad essa correlato.

        :param message_id: l'id del messaggio
        :returns: la proposta, se presente
        :rtype: Optional[Proposal]
        """
        try:
            proposal = self.proposals[messsage_id]
        except KeyError:
            return None
        else:
            return proposal

    def add_proposal(self, message: discord.Message) -> None:
        """Aggiunge la proposta al file proposals.json salvando timestamp
        e numero di membri attivi in quel momento.

        :param message: messaggio mandato nel canale proposte da aggiungere
        :param guild: il server discord
        """
        orator_count = 0
        for member in Config.get_config().guild.members:
            if (Config.get_config().orator_role in member.roles or
                    any(role in Config.get_config().moderation_roles for role in member.roles)):
                orator_count += 1
        proposal = Proposal(
            timestamp=message.created_at.date().isoformat(),
            total_voters=orator_count,
            threshold=(orator_count // 2 + 1),  # maggioranza assoluta
            content=message.content
        )
        self.proposals[message.id] = proposal
        self._save()

    def remove_proposal(self, message_id: int) -> None:
        """Rimuove la proposta con id uguale al messaggio passato dal file.
        Se non trovata non fa nulla.

        :param message: messaggio della proposta
        """
        try:
            del self.proposals[message_id]
        except KeyError:
            print('proposta non trovata')
        else:
            self._save()

    def adjust_vote_count(self, payload: discord.RawReactionActionEvent, change: int):
        """Aggiusta il contatore dei voti in base al parametro passato.
        Stabilisce in autonomia se il voto è a favore o contrario guardando
        il tipo di emoji cambiata.

        :param payload: l'evento di rimozione dell'emoji
        :param change: variazione del voto (+1 o -1)
        """
        proposal = self.get_proposal(payload.message_id)
        if proposal is None:
            print('impossibile trovare la proposta')
            return
        proposal.adjust_vote_count(payload.emoji.name, change)
        self._save()

    async def handle_proposals(self) -> None:
        """Gestisce le proposte, verificando se hanno raggiunto un termine."""
        class Report(TypedDict):
            result: str
            description: str
            colour: discord.Color
        to_delete = set()
        for key in self.proposals.keys():
            try:
                message = await Config.get_config().poll_channel.fetch_message(key)
            except discord.NotFound:
                # capita se viene cancellata dopo un riavvio o mentre è offline
                await BotLogger.get_instance().log('proposta già cancellata, ignoro')
                to_delete.add(key)
                continue
            proposal = self.proposals[key]
            if proposal.passed:
                report: Report = {
                    'result': 'passata',
                    'description': 'La soglia per la proposta è stata raggiunta.',
                    'colour': discord.Color.green()
                }
            elif proposal.rejected:
                report: Report = {
                    'result': 'bocciata',
                    'description': 'La proposta è stata bocciata dalla maggioranza.',
                    'colour': discord.Color.red()
                }
            elif date.today() - date.fromisoformat(proposal.timestamp) >= timedelta(days=Config.get_config().poll_duration):
                report: Report = {
                    'result': 'scaduta',
                    'description': 'La proposta non ha ricevuto abbastanza voti.',
                    'colour': discord.Color.gold()
                }
            else:
                # La proposta semplicemente è ancora in corso
                continue
            content = discord.Embed(
                title=f'Proposta {report["result"]}',
                description=report['description'],
                colour=report['colour']
            )
            content.add_field(
                name='Autore',
                value=f'{message.author.mention}',
                inline=False
            )
            msg_content = proposal.content
            if len(message.attachments):
                msg_content += ' [File in allegato]'
            content.add_field(
                name='Contenuto',
                value=msg_content,
                inline=False
            )
            attachments = [await a.to_file() for a in message.attachments]
            await Config.get_config().poll_channel.send(embed=content, files=attachments)
            await BotLogger.get_instance().log(f'proposta di {message.author.mention} {report["result"]}:\n\n{proposal.content}')
            await message.delete()
            to_delete.add(key)
        for key in to_delete:
            self.remove_proposal(key)
        self._save()

    def _save(self) -> None:
        """Salva su disco le modifiche effettuate alle proposte."""
        dict = {i: vars(p) for i, p in self.proposals.items()}
        sf.update_json_file(dict, 'proposals.json')