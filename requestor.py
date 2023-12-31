import httpx
import orjson
import logging

#==============================================================================#

ENC = 'utf-8'
HEADERS = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36', 
           'accept': 'application/json,text/*;q=0.99'}
PROXIES = None

#==============================================================================#

def serialize(obj) -> str:
    return orjson.dumps(obj, option=orjson.OPT_INDENT_2).decode(ENC)

def deserialize(json: str):
    return orjson.loads(json)

async def exec_method(base_url, method_type, method, client=None, headers=HEADERS, params=None, data=None,
                      files=None, proxies=PROXIES, astext=False):
    async def exec_(client_: httpx.AsyncClient):
        req = client_.build_request(method=method_type, url=method, params=params, json=data, files=files)
        logging.debug(f">>> {serialize({'url': str(req.url), 'headers': str(req.headers), 'data': data})}")
        res_obj = None
        res_text = ''
        try:
            res = await client_.send(req)
            if not res is None and res.is_success:
                res_text = res.text
                if not astext:
                    res_obj = res.json()            
                    logging.debug(f"<<< {res.status_code}: {serialize(res_obj)}")
            else:
                logging.debug(repr(res))
                logging.debug(res_text)
        except Exception as err:
            logging.exception(str(err) + '\n\n' + res_text, exc_info=False)
        return res_text if astext else res_obj

    if client is None:
        async with httpx.AsyncClient(headers=headers, base_url=base_url, proxies=proxies, verify=False) as client_:
            res = await exec_(client_)
    else:
        res = await exec_(client)
    return res

#==============================================================================#

class AsyncRequestor:

    def __init__(self, base_url: str):
        self._base_url = base_url
        self._make_headers()
        self._client = httpx.AsyncClient(headers=self._headers, base_url=self._base_url, proxies=PROXIES, verify=False)
        logging.debug('HTTPX CLIENT INITIALIZED')

    def _make_headers(self):
        self._headers = HEADERS

    async def exec_get(self, method, params=None, astext=False):
        return await exec_method(self._base_url, 'GET', method, self._client, params=params, astext=astext)
    
    async def exec_post(self, method, params=None, data=None, files=None, astext=False):
        return await exec_method(self._base_url, 'POST', method, self._client, params=params, data=data, files=files, astext=astext)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *excinfo):
        await self._client.aclose()
        logging.debug('HTTPX CLIENT FREED')