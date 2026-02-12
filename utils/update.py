"""Script di aggiornamento del bot."""
import json
import os
from typing import Any, Dict

from utils.paths import BASE_DIR, CONFIG_DIR, CONFIG_FILE, DATA_DIR


# Campi da aggiornare ad ogni release
lastest_fields = [
    'nickname',
    'last_nick_change',
    'violations_count',
    'last_violation_date',
    'bio',
    'orator',
    'orator_expiration',
    'orator_weekly_buffer',
    'orator_daily_buffer',
    'orator_last_message_timestamp',
    'orator_total_messages',
    'dank',
    'dank_expiration',
    'dank_messages_buffer',
    'dank_first_message_timestamp',
    'dank_total_messages'
]

# Campi fino alla ver. 2.0
fields_2_0 = [
    "nick",
    "last_nick_change",
    "mon",
    "tue",
    "wed",
    "thu",
    "fri",
    "sat",
    "sun",
    "counter",
    "last_message_date",
    "violations_count",
    "last_violation_date",
    "orator",
    "orator_expiration",
    "orator_total_messages",
    "dank",
    "dank_messages_buffer",
    "dank_first_message_timestamp",
    "dank_expiration",
    "dank_total_messages",
    "bio"
]


def run():
    """Esegue l'aggiornamento a versioni successive del bot."""
    # pre-2.0 -> 2.0+: nuovo schema per aflers
    if os.path.isfile('aflers.json'): # se non esiste => >=2.5
        aflers: Dict[str, Dict[str, Any]]
        try:
            with open('aflers.json', 'r') as file:
                aflers = json.load(file)
        except json.JSONDecodeError:
            print('aggiornamento non attuabile su archivio attuale perché corrotto')
            os.replace('aflers.json', 'aflers-not-upgraded.json')
        else:
            curr_fields = list(next(iter(aflers.values())).keys())
            if curr_fields == fields_2_0:
                print('========== Aggiornamento alla 2.0+ ==========')
                # Aggiorna alla >2.0
                aflers_new = {
                        id: from_2_0_to_lastest(values)
                        for id, values in aflers.items()
                }
                os.replace('aflers.json', 'aflers-old.json')
                with open('aflers.json', 'w+') as file:
                    json.dump(aflers_new, file, indent=4)
                print('========== Fine aggiornamento alla 2.0+ ==========')

    # <2.5 -> >=2.5: nuova posizione file
    if os.path.isfile('config.json') and not os.path.isfile(CONFIG_FILE):
        update_to_2_5()

def from_2_0_to_lastest(data: Dict[str, Any]) -> Dict[str, Any]:
    """Aggiorna il dizionario dell'afler dalla versione 2.0 all'ultima
    versione.
    """
    new_item = {}
    new_item['nickname'] = data['nick']
    new_item['last_nick_change'] = data['last_nick_change']
    new_item['violations_count'] = data['violations_count']
    new_item['last_violation_date'] = data['last_violation_date']
    new_item['bio'] = data['bio']
    new_item['orator'] = data['orator']
    new_item['orator_expiration'] = data['orator_expiration']
    new_item['orator_weekly_buffer'] = []
    new_item['orator_weekly_buffer'].append(data['mon'])
    new_item['orator_weekly_buffer'].append(data['tue'])
    new_item['orator_weekly_buffer'].append(data['wed'])
    new_item['orator_weekly_buffer'].append(data['thu'])
    new_item['orator_weekly_buffer'].append(data['fri'])
    new_item['orator_weekly_buffer'].append(data['sat'])
    new_item['orator_weekly_buffer'].append(data['sun'])
    new_item['orator_daily_buffer'] = data['counter']
    new_item['orator_last_message_timestamp'] = data['last_message_date']
    new_item['orator_total_messages'] = data['orator_total_messages']
    new_item['dank'] = data['dank']
    new_item['dank_expiration'] = data['dank_expiration']
    new_item['dank_messages_buffer'] = data['dank_messages_buffer']
    new_item['dank_first_message_timestamp'] = data['dank_first_message_timestamp']
    new_item['dank_total_messages'] = data['dank_total_messages']
    return new_item

def update_to_2_5():
    print('========== Aggiornamento alla versione 2.5+ ==========')

    # Sposta file di config
    os.rename('config.json', CONFIG_FILE)
    print(f'config.json spostato in {CONFIG_DIR.relative_to(BASE_DIR)}')

    # Sposta dati
    if not os.path.isdir(DATA_DIR):
        os.mkdir(DATA_DIR)
    data_files = ('aflers', 'banned_words', 'proposals', 'subreddits')
    for file in data_files:
        try:
            os.rename(f'{file}.json', f'{DATA_DIR}/{file}.json')
            print(f'{file}.json spostato in {DATA_DIR.relative_to(BASE_DIR)}')
        except FileNotFoundError:
            print(f'{file}.json non esiste, skip')
            pass
        except FileExistsError:
            print(f'{file}.json già presente in data, skip')

    print('========== Fine aggiornamento alla 2.5+ ==========')
