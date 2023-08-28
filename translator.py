import logging
from typing import Union

from config import CONFIG
from requestor import AsyncRequestor

#==============================================================================#

BASE_URL = 'https://translate.api.cloud.yandex.net/translate/v2'

#==============================================================================#

class Translator(AsyncRequestor):

    def __init__(self):
        super().__init__(BASE_URL)

    def _make_headers(self):
        super()._make_headers()
        self._headers |= {'Authorization': f'Api-Key {CONFIG.yandex_api_key.get_secret_value()}'}

    async def translate(self, texts: Union[str, list[str]], tolang='ru', fromlang=None) -> list[str]:
        if isinstance(texts, str):
            texts = [texts]
        payload = dict(texts=texts, targetLanguageCode=tolang.lower())
        if fromlang:
            payload['sourceLanguageCode'] = fromlang.lower()

        res = await self.exec_post('/translate', data=payload)
        if res is None or not res.get('translations', None): 
            logging.debug(f'Translator: Нет вариантов перевода')
            return []
        
        return [element.get('text', '') for element in res['translations']]
        
