"""Script di aggiornamento dell'archivio."""
import json
from os import replace
from typing import Any, Dict

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
    """Applica la patch al dizionario."""
    try:
        with open('utils/fields.json', 'r') as file:
            curr_fields = json.load(file)
    except FileNotFoundError:
        with open('utils/fields.json', 'w+') as file:
            json.dump(lastest_fields, file)
        return
    try:
        with open('aflers.json', 'r') as file:
            aflers = json.load(file)
    except FileNotFoundError:
        return
    except json.JSONDecodeError:
        print('aggiornamento non attuabile su archivio attuale perché corrotto')
        replace('aflers.json', 'aflers-not-upgraded.json')
        return
    if curr_fields == lastest_fields:
        return
    if curr_fields == fields_2_0:
        aflers_new = {id: from_2_0_to_lastest(
            values) for id, values in aflers.items()}
    else:
        return
    replace('aflers.json', 'aflers-old.json')
    with open('aflers.json', 'w+') as file:
        json.dump(aflers_new, file, indent=4)
    replace('utils/fields.json', 'utils/fields-old.json')
    with open('utils/fields.json', 'w+') as file:
        json.dump(lastest_fields, file, indent=4)


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
