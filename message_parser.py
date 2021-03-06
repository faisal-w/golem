from wit import Wit
import dateutil.parser
import re
from datetime import timedelta
import datetime
import emoji

def teach_wit(wit_token, entity, values, doc=""):
    import requests
    print('*** TEACHING WIT ***')
    params = {'v':'20160516'}
    rsp = requests.request(
        'PUT',
        'https://api.wit.ai/entities/'+entity,
        headers={
            'authorization': 'Bearer ' + wit_token,
            'accept': 'application/json'
        },
        params=params,
        json={'doc':doc, 'values':values}
    )
    if rsp.status_code > 200:
        raise ValueError('Wit responded with status: ' + str(rsp.status_code) +
                       ' (' + rsp.reason + ')')
    json = rsp.json()
    if 'error' in json:
        raise ValueError('Wit responded with an error: ' + json['error'])

def parse_text_message(config, text, num_tries=1):
    try:
        wit_client = Wit(access_token=config['WIT_TOKEN'], actions={})
        wit_parsed = wit_client.message(text)
        #print(wit_parsed)
    except Exception as e:
        print('WIT ERROR: ', e)
        # try to parse again 5 times
        if num_tries > 5:
            raise
        else:
            return parse_text_message(config, text, num_tries=num_tries+1)

    entities = wit_parsed['entities']
    print('WIT ENTITIES:', entities)
    append = parse_additional_entities(text)
    for entity,values in entities.items():
        # parse datetimes to date_intervals
        if entity == 'datetime':
            append['date_interval'] = []
            for value in values:
                try:
                    if value['type'] == 'interval':
                        date_from = dateutil.parser.parse(value['from']['value'])
                        date_to = dateutil.parser.parse(value['to']['value'])
                        grain = value['from']['grain']
                    else:
                        grain = value['grain']
                        date_from = dateutil.parser.parse(value['value'])
                        date_to = date_from + timedelta_from_grain(grain)
                        if 'datetime' not in append:
                            append['datetime'] = []
                        append['datetime'].append({'value':date_from, 'grain':grain})
                    formatted = format_date_interval(date_from, date_to, grain)
                    append['date_interval'].append({'value':(date_from, date_to), 'grain':grain, 'formatted':formatted})
                except ValueError as e:
                    print('Error parsing date {}: {}', value, e)

    if 'datetime' in entities:
        del entities['datetime']

    for (entity, value) in re.findall(re.compile(r'/([^/]+)/([^/]+)/'), text):
        if not entity in append:
            append[entity] = []
        append[entity].append({'value': value})

    # add all new entity values
    for entity,values in append.items():
        if not entity in entities:
            entities[entity] = []
        entities[entity] += values

    entities['_message_text'] = [{'value':text}]
    return {'entities':entities, 'type':'message'}

def parse_additional_entities(text):
    entities = {'emoji':[], 'intent':[]}
    chars = {':)':':slightly_smiling_face:', '(y)':':thumbs_up_sign:', ':(':':disappointed_face:',':*':':kissing_face:',':O':':face_with_open_mouth:',':D':':grinning_face:','<3':':heavy_black_heart:️',':P':':face_with_stuck-out_tongue:'}
    demojized = emoji.demojize(text)
    char_emojis = re.compile(r'(' + '|'.join(chars.keys()).replace('(','\(').replace(')','\)').replace('*','\*') + r')')
    demojized = char_emojis.sub(lambda x: chars[x.group()], demojized)
    if demojized != text:
        match = re.compile(r':([a-zA-Z_0-9]+):')
        for emoji_name in re.findall(match, demojized):
            entities['emoji'].append({'value':emoji_name})
        #if re.match(match, demojized):
        #    entities['intent'].append({'value':'emoji'})
    return entities

def timedelta_from_grain(grain):
    if grain=='second':
        return timedelta(seconds=1)
    if grain=='minute':
        return timedelta(minutes=1)
    if grain=='hour':
        return timedelta(hours=1)
    if grain=='day':
        return timedelta(days=1)
    if grain=='week':
        return timedelta(days=7)
    if grain=='month':
        return timedelta(days=31)
    if grain=='year':
        return timedelta(days=365)
    return timedelta(days=1)

def date_now(tzinfo):
    return datetime.datetime.now(tzinfo)

def date_today(tzinfo):
    return date_now(tzinfo).replace(hour=0, minute=0, second=0, microsecond=0)

def date_this_week(tzinfo):
    today = date_today(tzinfo)
    return today - timedelta(days=today.weekday())

def format_date_interval(from_date, to_date, grain):
    tzinfo = from_date.tzinfo
    now = date_now(tzinfo)
    today = date_today(tzinfo)
    this_week = date_this_week(tzinfo)
    next_week = this_week + timedelta(days=7)
    diff_hours = (to_date-from_date).total_seconds() / 3600
    print('Diff hours: %s' % diff_hours)

    if grain in ['second','minute'] and (now-from_date).total_seconds() < 60*5:
        return 'now'

    for i in range(0,6):
        # if the dates are within the i-th day
        if from_date >= today+timedelta(days=i) and to_date <= today+timedelta(days=i+1):
            if i==0:
                day = 'today'
            elif i==1:
                day = 'tomorrow'
            else:
                day = '%s' % from_date.strftime("%A")
            if from_date.hour >= 17:
                return 'this evening' if i==0 else day+' evening'
            if from_date.hour >= 12:
                return 'this afternoon' if i==0 else day+' afternoon'
            if to_date.hour >= 0 and to_date.hour < 13 and to_date.hour>0:
                return 'this morning' if i==0 else day+' morning'
            return day

    if from_date == this_week and to_date == next_week:
        return 'this week'

    if from_date == next_week and to_date == next_week+timedelta(days=7):
        return 'next week'

    if diff_hours<=25: # (25 to incorporate possible time change)
        digit = from_date.day % 10
        date = 'the {}{}'.format(from_date.day, 'st' if digit==1 else ('nd' if digit==2 else 'th'))
        return date if from_date.month==now.month else date+' '+from_date.strftime('%B')
    return 'these dates'
