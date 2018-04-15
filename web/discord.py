import requests
import datetime
import json

def send_application(url, vote_link, token, name='', position=None):

    request = {
            'content': '',
            'embeds': [
                {
                    'title': 'New application received!',
                    'icon_url': '',
                    'timestamp': datetime.datetime.utcnow().isoformat(),
                    'description':
                    ('`{name}` has applied' + (' for '+position if position is not None else '') + 
                    '!\n'
                    '[Admin panel]({vote_link}/{token})\n'
                    '[Member voting]({vote_link})'
                    '').format(name=name, vote_link=vote_link, token=token)
                }
            ]
    }

    headers = {'Content-Type': 'application/json'}

    request = json.dumps(request)
    response = requests.post(url, data=request, headers=headers)
    print('Sent discord webhook, response was ' + str(response))

