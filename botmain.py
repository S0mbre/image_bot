import logging
import asyncio
import re
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
# from aiogram.utils import markdown as md
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import (ReplyKeyboardMarkup, InlineKeyboardMarkup, KeyboardButton, InlineKeyboardButton, 
                           Message, BufferedInputFile, ReplyKeyboardRemove, CallbackQuery)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.chat_action import ChatActionMiddleware, ChatActionSender
from io import BytesIO

from config import CONFIG
import imgsearch
import imgcap
import imgsimilar

# ============================================================ #

BOT_HELP = \
"""
Отправь описание картинки, например "жёлтый экскаватор", бот вернёт картинки (от 1 до 50). 
Отправь боту картинку, бот вернёт её описание.
"""

BTNS_NUMBER_IMAGES = ['1', '3', '5', '7', '10', '15', '20', '30', '40', '50', '❌ Отмена']
BTNS_IMG_ACTIONS = ['✍\nОписание', '❓\nВопрос', '👥\nПохожие', '❌ Отмена']
NL = '\n'
INFLECT_REPLY = {'1': 'картинка', '2': 'картинки', '3': 'картинки', '4': 'картинки'}

# ============================================================ #

logging.basicConfig(level=logging.INFO)

bot = Bot(token=CONFIG.bot_token.get_secret_value())
dp = Dispatcher(storage=MemoryStorage())
dp.message.middleware(ChatActionMiddleware())

# ============================================================ #

class MyStates(StatesGroup):
    start_state = State()
    search_state = State()
    img_load_state = State()
    # img_summary_state = State()
    img_question_state = State()
    # img_findsimilar_state = State()

# ============================================================ #

def make_keyboard(items: list[str], placeholder: str = 'Выберите действие', cols: int = 3) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(*[KeyboardButton(text=item) for item in items])
    builder.adjust(min(cols, len(items)))
    return builder.as_markup(resize_keyboard=True, input_field_placeholder=placeholder or None)

def make_keyboard_inline(items: list[dict], cols: int = 3) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(*[InlineKeyboardButton(**item) for item in items])
    builder.adjust(min(cols, len(items)))
    return builder.as_markup(resize_keyboard=True)

def inflect_num(num: int) -> str:
    last = str(num)[-1]
    return INFLECT_REPLY.get(last, 'картинок')

# ================ 1 - СТАРТ

@dp.message(Command(commands=['start', 'help']))
async def start(message: Message, state: FSMContext):
    if message.text != '/help':
        await state.clear()
        await state.set_state(MyStates.start_state)
    await message.answer(BOT_HELP)

# ================ 2 - ПОИСК КАРТИНОК ПО ТЕКСТУ

async def send_images(q: str, num: int, message: Message, state: FSMContext):    
    results = imgsearch.search(q=q, num=num)
    if results:
        for i, res in enumerate(results):
            reply_markup = ReplyKeyboardRemove() if i == 0 else None
            try:
                await message.answer_photo(BufferedInputFile(res.img, res.filename), 
                                           reply_markup=reply_markup)
            except Exception as err:
                logging.exception(err, exc_info=False)
                # await message.answer(f'😩 Не смог загрузить изображение {i+1}', reply_markup=reply_markup)
                continue
    else:
        await message.answer('🤔 Картинки не найдены', reply_markup=ReplyKeyboardRemove())
    await state.clear()
    await state.set_state(MyStates.start_state)

async def process_image_search(q: str, state: FSMContext, message: Message = None, callback: CallbackQuery = None):
    msg = message or callback.message
    try:
        num = int(msg.text if message else callback.data)
    except ValueError:
        await message.answer('⛔ Надо указать ЧИСЛО картинок, например 3', 
                            reply_markup=ReplyKeyboardRemove())
        return

    if num < 1:
        await state.clear()
        await state.set_state(MyStates.start_state)
        await msg.answer('🤷 Нет так нет...', reply_markup=ReplyKeyboardRemove())
        return
    if num > imgsearch.MAX_NUMBER:
        await msg.answer(f'⚠ Будет показано не более {imgsearch.MAX_NUMBER} картинок', reply_markup=ReplyKeyboardRemove())
    if num > 14:
        await msg.answer(f'⏳ Поиск {num} картинок займет какое-то время ...', reply_markup=ReplyKeyboardRemove())
    await msg.answer(f'🔎 Ищу "{q}" в Google ({num} {inflect_num(num)}) ...', 
                            reply_markup=ReplyKeyboardRemove())
    
    await send_images(q, num, msg, state)

@dp.message(MyStates.start_state, F.text)
async def search_images_get_query(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(MyStates.search_state)
    await state.update_data({'q': message.text})
    await message.answer(f'❓ Сколько картинок найти (от 1 до {imgsearch.MAX_NUMBER})?{NL}Нажми или отправь "отмена" для отмены поиска.', 
                         reply_markup=make_keyboard_inline([{'text': s, 'callback_data': s} for s in BTNS_NUMBER_IMAGES], 5))
    
@dp.message(MyStates.search_state, F.text.regexp(r'(\d+)|(.*отмена)', flags=re.I))
async def search_images_process_query(message: Message, state: FSMContext, bot: Bot):    
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id, interval=2.0):
        data = await state.get_data()
        if not 'q' in data:
            await state.clear()
            await state.set_state(MyStates.start_state)
            await message.answer('⛔ Не указана ключевая фраза для поиска', 
                                reply_markup=ReplyKeyboardRemove())
            return
        if message.text.lower() == 'отмена':
            await state.clear()
            await state.set_state(MyStates.start_state)
            await message.answer('🤷 Нет так нет...', reply_markup=ReplyKeyboardRemove())
        else:
            await process_image_search(data['q'], state, message)

@dp.callback_query(MyStates.search_state, F.data.regexp(r'(\d+)|(.*отмена)', flags=re.I))
async def search_images_process_query_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):    
    async with ChatActionSender.typing(bot=bot, chat_id=callback.message.chat.id, interval=2.0):
        data = await state.get_data()
        if not 'q' in data:
            await state.clear()
            await state.set_state(MyStates.start_state)
            await callback.message.answer('⛔ Не указана ключевая фраза для поиска', 
                                          reply_markup=ReplyKeyboardRemove())
            await callback.answer()
            return
        if callback.data.lower() == 'отмена':
            await state.clear()
            await state.set_state(MyStates.start_state)
            await callback.message.answer('🤷 Нет так нет...', reply_markup=ReplyKeyboardRemove())
        else:
            await process_image_search(data['q'], state, None, callback)
        await callback.answer()   

# ================ 3 - ЗАГРУЗКА КАРТИНКИ

@dp.message(MyStates.start_state, F.photo)
async def image_load(message: Message, state: FSMContext, bot: Bot):
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id, interval=2.0):
        await state.clear()
        await state.set_state(MyStates.img_load_state)
        await message.answer(f'⏳ Пять сек, загружаю картинку ...', reply_markup=ReplyKeyboardRemove())

        try:
            my_bytes_io: BytesIO = await bot.download(message.photo[-1])
            await state.update_data({'pic': my_bytes_io.getvalue()})
        except Exception as err:
            await state.clear()
            await state.set_state(MyStates.start_state)
            await message.answer(f'⛔ {str(err)}', reply_markup=ReplyKeyboardRemove())
            return
        finally:
            my_bytes_io.close()

        await message.answer('❓ Что делаем дальше?                        -', 
                            reply_markup=make_keyboard_inline([{'text': s, 'callback_data': s} for s in BTNS_IMG_ACTIONS], 3))

# ================ 4 - ПОЛУЧЕНИЕ ОПИСАНИЯ ИЛИ ОТВЕТ НА ВОПРОС К КАРТИНКЕ

@dp.callback_query(MyStates.img_load_state, F.data.in_(BTNS_IMG_ACTIONS))
async def image_process_action(callback: CallbackQuery, state: FSMContext, bot: Bot):
    async with ChatActionSender.typing(bot=bot, chat_id=callback.message.chat.id, interval=2.0):
        data = await state.get_data()
        if not 'pic' in data:
            await state.clear()
            await state.set_state(MyStates.start_state)
            await callback.message.answer('⛔ Изображение не сохранено, попробуй загрузить заново', 
                                          reply_markup=ReplyKeyboardRemove())
            await callback.answer()
            return
        
        pic: bytes = data['pic']

        if callback.data.endswith('писание'):
            await callback.message.answer(f'⏳ Чуточку подождём (до 3 минут) ...', reply_markup=ReplyKeyboardRemove())
            if not 'imcap' in data:
                bio = BytesIO(pic)
                await state.update_data({'imcap': imgcap.Imgcap(bio)})
                bio.close()
                data = await state.get_data()
            imcap = data['imcap']
            summary = await imcap.summary(3)
            await callback.message.answer('. '.join(summary) if summary else '🤔 Описание не найдено', reply_markup=ReplyKeyboardRemove())
            await callback.message.answer('❓ Еще что-то?                                     -', 
                                          reply_markup=make_keyboard_inline([{'text': s, 'callback_data': s} for s in BTNS_IMG_ACTIONS], 3))
            await callback.answer()
            return

        elif callback.data.endswith('опрос'):
            if not 'imcap' in data:
                await callback.message.answer(f'⏳ Пять сек ...', reply_markup=ReplyKeyboardRemove())
                bio = BytesIO(pic)
                await state.update_data({'imcap': imgcap.Imgcap(bio)})
                bio.close()
                data = await state.get_data()
            imcap = data['imcap']
            await callback.message.answer('Задай свой вопрос 👇', reply_markup=ReplyKeyboardRemove())
            await state.set_state(MyStates.img_question_state)
            await state.update_data({'imcap': imcap})
            await callback.answer()
            return

        elif callback.data.endswith('охожие'):
            await callback.message.answer(f'⏳ Чуточку подождём (до 3 минут) ...', reply_markup=ReplyKeyboardRemove())
            try:
                imsim = imgsimilar.Imgsimilar()            
                result: imgsimilar.SimilarResult = await imsim.upload_and_parse(data['pic'])
            except Exception as err:
                logging.debug(err, exc_info=True)
                await state.clear()
                await state.set_state(MyStates.start_state)
                await callback.message.answer('⛔ Ошибка при поиске похожих картинок', 
                                              reply_markup=ReplyKeyboardRemove())
                await callback.answer()
                return
            else:
                sreply = ''
                if result.title and result.subtitle:
                    sreply += f'{result.title} - {result.subtitle}{NL}'
                if result.tags:
                    sreply += '🟢 ' + f'{NL}🟢 '.join(result.tags) + NL
                if result.similar:
                    sreply += f'Найдено {len(result.similar)} похожих изображений'
                await callback.message.answer(sreply, 
                                              reply_markup=make_keyboard_inline([{'text': '🔺 Открыть ссылку', 'url': result.url}], 1))
                await callback.message.answer('❓ Еще что-то?                                     -', 
                                              reply_markup=make_keyboard_inline([{'text': s, 'callback_data': s} for s in BTNS_IMG_ACTIONS], 3))
                await callback.answer()
                return
        
        await state.clear()
        await state.set_state(MyStates.start_state)
        await callback.message.answer('🤷 Нет так нет...', reply_markup=ReplyKeyboardRemove())
        await callback.answer()

# ================ 5 - ОТВЕТ НА ВОПРОС К КАРТИНКЕ

@dp.message(MyStates.img_question_state, F.text)
async def image_answer(message: Message, state: FSMContext, bot: Bot):
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id, interval=2.0):
        data = await state.get_data()
        if not 'imcap' in data:
            await state.clear()
            await state.set_state(MyStates.start_state)
            await message.answer('⛔ Изображение не сохранено, попробуй загрузить заново', 
                                 reply_markup=ReplyKeyboardRemove())
            return
        
        imcap: imgcap.Imgcap = data['imcap']

        await message.answer(f'⏳ Чуточку подождём (до 3 минут) ...', reply_markup=ReplyKeyboardRemove())
        answer = await imcap.answer(message.text, 'ru')
        await message.answer(answer or '🤔 Ответ не найден', reply_markup=ReplyKeyboardRemove())
        await state.set_state(MyStates.img_load_state)
        await message.answer('❓ Еще что-то?                                     -', 
                             reply_markup=make_keyboard_inline([{'text': s, 'callback_data': s} for s in BTNS_IMG_ACTIONS], 3))


# ============================================================ #

async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())