from pydrive.drive import GoogleDrive
from pydrive.auth import GoogleAuth
from oauth2client.service_account import ServiceAccountCredentials
from typing import Union, Optional
from pathlib import Path
from pydantic import BaseModel
import httpx, io, os, uuid, mimetypes, tempfile, logging

#==============================================================================#

GOOGLE_SECRETS = 'gsecrets.json'
GOOGLE_SCOPE = ['https://www.googleapis.com/auth/drive']
mimetypes.init()

#==============================================================================#

class Gfile(BaseModel):
    title: Optional[str] = None
    mime: Optional[str] = None
    id: Optional[str] = None
    url: Optional[str] = None

    def __str__(self):
        return f'{self.id} - {self.title} ({self.mime}): {self.url}'

#==============================================================================#

class Gdrive:

    def update_creds(self):
        logging.debug('Gdrive: Получение ключа аутентификации ...')
        gauth = GoogleAuth()
        gauth.credentials = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SECRETS, GOOGLE_SCOPE)
        self._gdrive = GoogleDrive(gauth)
        logging.debug('Gdrive: Ключ аутентификации получен')

    @staticmethod
    def generate_uid():
        return uuid.uuid4().hex

    @staticmethod
    async def download(url: str, filetype: str = 'bytes', **kwargs):
        async with httpx.AsyncClient(**kwargs) as client:
            r = await client.get(url)
            # assert r.status_code == 200
            if filetype == 'bytes':
                return r.read()
            if filetype == 'file':
                file_ = r.read()
                return io.BytesIO(file_)
            if filetype == 'text':
                return r.text
            if filetype == 'json':
                return r.json()
            
    @staticmethod
    def get_file_mime(file: str) -> tuple:
        logging.debug(f'Gdrive: Получение MIME файла "{file}" ...')
        content_type = mimetypes.guess_type(file, False)[0]
        ext = mimetypes.guess_extension(content_type) if content_type else ''
        logging.debug(f'Gdrive: Получение MIME файла "{file}" - ГОТОВО')
        return (content_type, ext)

    @staticmethod        
    async def get_file_name_and_content(file: Union[bytes, str]) -> tuple:
        logging.debug('Gdrive: Получение имени и MIME файла ...')
        name = Gdrive.generate_uid()
        content = None
        if isinstance(file, str):
            file = file.lower()
            if file.startswith('http') or file.startswith('ftp'):
                content = await Gdrive.download(file)
                f_, fpath = tempfile.mkstemp()
                with open(f_, 'wb') as f__:
                    f__.write(content)
                content_type, ext = Gdrive.get_file_mime(fpath)
                try: 
                    os.unlink(fpath)
                except:
                    pass
            else:
                pf = Path(file)
                content = pf.read_bytes()
                content_type, ext = Gdrive.get_file_mime(str(pf)) 
        else:
            try:
                f_, fpath = tempfile.mkstemp()
                with open(f_, 'wb') as f__:
                    f__.write(file)
                content_type, ext = Gdrive.get_file_mime(fpath) 
                try: 
                    os.unlink(fpath)
                except:
                    pass
            except Exception as err:
                logging.exception(err, exc_info=True)
        
        logging.debug('Gdrive: Получение имени и MIME файла - ГОТОВО')
        return (name + ext, content_type, content or file)

    async def upload(self, file: Union[str, bytes], replace_id: Optional[str] = None, mimetype: Optional[str] = None) -> Gfile:
        self.update_creds()
        logging.debug('Gdrive: Загрузка файла ...')
        fname, mime, content = await Gdrive.get_file_name_and_content(file)
        f = self._gdrive.CreateFile({'id': replace_id} if replace_id else {'title': fname})
        if f['title'] != fname: f['title'] = fname
        f['mimetype'] = mimetype or mime
        f.content = io.BytesIO(content)
        f.Upload()
        f.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
        file_id = f['id']
        filemodel = Gfile(title=f['title'], mime=f['mimetype'], id=file_id, url=f'https://drive.google.com/uc?id={file_id}&export=download')
        f = None
        logging.debug('Gdrive: Загрузка файла - ГОТОВО')
        return filemodel

    async def delete(self, file_id: str, permanent: bool = True):
        self.update_creds()
        logging.debug(f'Gdrive: Удаление файла {file_id} ...')
        f = self._gdrive.CreateFile({'id': file_id})
        if permanent:
            f.Delete()
        else:
            f.Trash()
        logging.debug(f'Gdrive: Удаление файла {file_id} - ГОТОВО')

    async def getmeta(self, file_id: str) -> dict:
        self.update_creds()
        f = self._gdrive.CreateFile({'id': file_id})
        f.FetchMetadata(fetch_all=True)
        meta = f.metadata
        f = None
        return meta
    
    def geturl(self, file_id: str) -> str:
        return f'https://drive.google.com/uc?id={file_id}&export=download'

    async def download(self, file_id: str, filetype: str = 'bytes'):
        self.update_creds()
        f = self._gdrive.CreateFile({'id': file_id})
        f.FetchContent()
        if filetype == 'file':
            content = f.content
        elif filetype == 'bytes':
            content = f.content.read()
        else:
            content = f.GetContentString()
        f = None
        return content
