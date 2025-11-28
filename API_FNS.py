import requests
from pprint import pprint
import http

url = ' https://api-fns.ru/api/search'

payload = {
    'q': 'Стоматология',
    'page': 1,
    'key': 'c5d950f0bba7be07e86317e91980706a1f644331',
    'region': '55'

}
resp = requests.get(url, params=payload)

print(resp.url)
pprint(resp.json())