from bs4 import BeautifulSoup
from pydantic import BaseModel
from typing import Optional, List, Union
import logging

from requestor import AsyncRequestor
from gdrive import Gdrive

#==============================================================================#

BASE_URL = 'https://yandex.ru/images/search'
MAX_SIMILAR = 20
NL = '\n'
DRIVE = Gdrive()

#==============================================================================#

class SimilarResult(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    tags: List[str] = []
    similar: List[str] = []
    url: Optional[str] = None

    def __str__(self):
        return f'{self.title} - {self.subtitle}{NL}{", ".join(self.tags)}{NL}{len(self.similar)} похожих{NL}{self.url}'

#==============================================================================#

class Imgsimilar(AsyncRequestor):

    def __init__(self, max_similar: int = MAX_SIMILAR):
        super().__init__(BASE_URL)
        self._max_similar = max_similar or MAX_SIMILAR

    async def _get_url(self, url: str) -> str:
        logging.debug(f'Imgsimilar: Загрузка страницы "{url}" ...')
        return await self.exec_get('', {'source': 'collections', 'rpt': 'imageview', 'url': url}, True)

    def _parse_result(self, html: str) -> SimilarResult:
        logging.debug('Imgsimilar: Парсинг HTML ...')
        soup = BeautifulSoup(html, 'lxml')

        url = soup.find('img', class_='CbirPreview-Image')
        if url: 
            url = url.get('src')

        title = soup.find('h2', class_='CbirObjectResponse-Title')
        if title: 
            title = title.text.capitalize().strip('. ')

        subtitle = soup.find('div', class_='CbirObjectResponse-Description')
        if subtitle: 
            subtitle = subtitle.text.capitalize().strip('. ')

        tags_div = soup.find('div', class_='Tags Tags_type_expandable Tags_view_buttons')
        tags = []
        if tags_div:
            tags_ = tags_div.find_all('span', class_='Button2-Text')
            if tags_:
                tags = [t.text.capitalize() for t in tags_]

        thumbs_div = soup.find('div', class_='CbirSimilar-Thumbs')
        similar = []
        if thumbs_div:            
            similar_ = thumbs_div.find_all('div', class_='MMImage MMImage_type_cover Thumb-Image')
            if similar_:
                for s in similar_:
                    ss = s.get('style')
                    if ':url(' in ss: similar.append('https:' + ss.split('(')[1][:-1])
        if similar: similar = similar[:self._max_similar]
        logging.debug('Imgsimilar: Парсинг завершен')
        return SimilarResult(title=title, subtitle=subtitle, tags=tags, similar=similar, 
                             url=f'{BASE_URL}?source=collections&rpt=imageview&url={url}' if url else None)
    
    async def parse(self, url: str) -> SimilarResult:
        html = await self._get_url(url)
        return self._parse_result(html)
    
    async def upload_and_parse(self, file: Union[str, bytes]) -> SimilarResult:
        logging.debug('Imgsimilar: Загружаю картинку в Google Drive ...')
        gfile = await DRIVE.upload(file)
        logging.debug(f'Imgsimilar: Загружено в Google Drive: {str(gfile)}')        
        res = await self.parse(gfile.url)
        await DRIVE.delete(gfile.id)
        return res
    
# ============================================================ #

# import asyncio

# async def main():
#     p = r'c:\И\аэаэ\12.JPG'
#     imsim = Imgsimilar(6)
#     sim = await imsim.upload_and_parse(p)
#     print(sim)
#     print(repr(sim.similar))

# if __name__ == '__main__':
#     asyncio.run(main())