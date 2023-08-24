from google_images_search import GoogleImagesSearch
from io import BytesIO
from PIL import Image
from pydantic import BaseModel
import logging
from pathlib import Path
import mimetypes

from config import CONFIG

# ============================================================ #
# https://github.com/arrrlo/Google-Images-Search
# _search_params = {
#     'q': '...',
#     'num': 10,
#     'fileType': 'jpg|gif|png',
#     'rights': 'cc_publicdomain|cc_attribute|cc_sharealike|cc_noncommercial|cc_nonderived',
#     'safe': 'active|high|medium|off|safeUndefined', ##
#     'imgType': 'clipart|face|lineart|stock|photo|animated|imgTypeUndefined', ##
#     'imgSize': 'huge|icon|large|medium|small|xlarge|xxlarge|imgSizeUndefined', ##
#     'imgDominantColor': 'black|blue|brown|gray|green|orange|pink|purple|red|teal|white|yellow|imgDominantColorUndefined', ##
#     'imgColorType': 'color|gray|mono|trans|imgColorTypeUndefined' ##
# }

OPT_FILETYPE = 'jpg|gif|png'
OPT_SAFE = 'medium'
OPT_RIGHTS = None
OPT_IMGTYPE = 'imgTypeUndefined'
OPT_IMGSIZE = 'imgSizeUndefined'
OPT_COLOR = 'imgDominantColorUndefined'
OPT_COLORTYPE = 'imgColorTypeUndefined'
DEFAULT_NUMBER = 10
MAX_NUMBER = 50
MAX_IMGSIZE = 800
ENC = 'utf-8'
DEBUG = False

mimetypes.init()
logging.basicConfig(filename=str(Path(__file__).parent / 'log.log'), filemode='w', style='{',
                    format='[{asctime}] [{levelname}] {message}', datefmt='%d.%m.%Y %H:%M:%S',
                    encoding=ENC, level=logging.DEBUG if DEBUG else logging.INFO)

# ============================================================ #

class SimpleImage(BaseModel):
    img: bytes
    mime: str
    filename: str

    def __str__(self):
        return f'{self.filename} ({self.mime}) - {len(self.img)} b'

# ============================================================ #

def resize_img(img: Image, max_dimension: int) -> Image:
    w, h = img.size
    res_ratio = min(max_dimension/w, max_dimension/h)
    new_size = tuple(round(x * res_ratio) for x in (w, h))
    return img.resize(new_size) if res_ratio < 1.0 else img

# ============================================================ #

def search(q: str, num: int = DEFAULT_NUMBER, fileType: str = OPT_FILETYPE, rights: str = OPT_RIGHTS,
           safe: str = OPT_SAFE, imgType: str = OPT_IMGTYPE, imgSize: str = OPT_IMGSIZE, 
           imgDominantColor: str = OPT_COLOR, imgColorType: str = OPT_COLORTYPE, 
           max_dimension: int = MAX_IMGSIZE) -> list[SimpleImage]:
    if num < 1: return []
    params = {'q': q, 'num': min(num, MAX_NUMBER), 'fileType': fileType, 'rights': rights, 
              'safe': safe, 'imgType': imgType, 'imgSize': imgSize, 
              'imgDominantColor': imgDominantColor, 'imgColorType': imgColorType}
    logging.info('Поиск изображений:\n' + repr(params))
    try:
        gis = GoogleImagesSearch(CONFIG.google_api_key.get_secret_value(), CONFIG.google_cx.get_secret_value())
        gis.search(params)
    except Exception as err:
        logging.exception(err)
        return []
    else:
        results = []
        for i, image in enumerate(gis.results()):
            logging.debug(f'Обработка изображения [{i}]: {image.url} ...') 
            my_bytes_io = BytesIO()
            try:                            
                image.copy_to(my_bytes_io)
                my_bytes_io.seek(0)
                img = Image.open(my_bytes_io)
                mime = img.format
                ext = mimetypes.guess_extension(Image.MIME[mime], False)
                img = resize_img(img, max_dimension)
                my_bytes_io.seek(0)
                img.save(my_bytes_io, mime)
                res_img = SimpleImage(img=my_bytes_io.getvalue(), mime=mime, filename=f'{i:02}{ext}')
                logging.debug(str(res_img))
                results.append(res_img)
                logging.debug(f'Изображение [{i}] СОХРАНЕНО')
            except Exception as err:
                logging.exception(err)                
            finally:
                my_bytes_io.close()
        return results