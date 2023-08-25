import torch
from PIL import Image
from typing import Union, BinaryIO, Optional
from lavis.models import load_model_and_preprocess
import os
import logging

from translator import Translator

# ============================================================ # 
# https://github.com/salesforce/LAVIS#image-captioning

os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = 'true'

# ============================================================ #

class Imgcap:

    def __init__(self, source_image: Optional[Union[str, bytes, BinaryIO]]):
        logging.debug('Imgcap: Инициализация объекта ...')
        self.image = None        
        self._device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        cap = load_model_and_preprocess(name='blip_caption', model_type='large_coco', is_eval=True, device=self._device)
        vqa = load_model_and_preprocess(name='blip_vqa', model_type='vqav2', is_eval=True, device=self._device)        
        self._cap_model = cap[0]
        self._cap_vis_processors = cap[1]
        self._cap_txt_processors = cap[2]
        self._vqa_model = vqa[0]
        self._vqa_vis_processors = vqa[1]
        self._vqa_txt_processors = vqa[2]
        self.load(source_image)
        logging.debug('Imgcap: Объект создан')

    def __del__(self):
        if not self.image is None:
            self.image.close()
        logging.debug('Imgcap: Объект уничтожен')

    def load(self, img: Optional[Union[str, bytes, BinaryIO]]):
        if not self.image is None:
            self.image.close()
        if not img is None: 
            logging.debug('Imgcap: Загрузка нового изображения ...')
            self.image = Image.open(img).convert('RGB')
            self._cap_image = self._cap_vis_processors['eval'](self.image).unsqueeze(0).to(self._device)
            self._vqa_image = self._vqa_vis_processors['eval'](self.image).unsqueeze(0).to(self._device)
            logging.debug('Imgcap: Изображение загружено в память')

    async def translate(self, texts: Union[str, list[str]]) -> list[str]:
        async with Translator() as tr:
            results = await tr.translate(texts, 'ru', 'en')
        return results
    
    def capitalize(self, results: Union[str, list[str]]) -> list[str]:
        if isinstance(results, str):
            results = [results]
        return [s.capitalize() for s in results]

    async def summary(self, number: int = 1) -> list[str]:
        logging.info('Imgcap: Генерация описания для изображения ...')
        results = self._cap_model.generate({'image': self._cap_image}, use_nucleus_sampling=True, num_captions=number)
        logging.info(f'Imgcap: Описания сгенерированы: {repr(results)}')
        results = await self.translate(results)
        results = self.capitalize(results)
        logging.info(f'Imgcap: Описания переведены: {repr(results)}')
        return results
    
    async def answer(self, question: str) -> str:
        logging.info(f'Imgcap: Генерация ответа на вопрос "{question}" ...')
        q = self._vqa_txt_processors['eval'](question)
        samples = {'image': self._vqa_image, 'text_input': q}
        reply = self._vqa_model.predict_answers(samples=samples, inference_method='generate')
        res = reply[0] if reply else ''
        logging.info(f'Imgcap: Ответ на вопрос "{question}" сгенерирован: "{res}"')
        results = await self.translate(res)
        logging.info(f'Imgcap: Ответ переведен: {repr(results)}')
        results = self.capitalize(results)
        res = results[0] if results else ''
        return res
    
# ============================================================ #

import asyncio

async def main():
    p = r'c:\И\аэаэ\06.JPG'
    imcap = Imgcap(p)
    summary = await imcap.summary(3)
    print(summary)

if __name__ == '__main__':
    asyncio.run(main())