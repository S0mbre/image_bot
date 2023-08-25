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

# ============================================================ #

BOT_HELP = \
"""
Отправь описание картинки, например "жёлтый экскаватор", бот вернёт картинки (от 1 до 50). 
Отправь боту картинку, бот вернёт её описание.
"""

BTNS_NUMBER_IMAGES = ['1', '3', '5', '7', '10', '15', '20', '30', '40', '50', 'Отмена']
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
    img_search_state = State()

# ============================================================ #

def make_keyboard(items: list[str], placeholder: str = 'Выберите действие', cols: int = 3) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(*[KeyboardButton(text=item) for item in items])
    builder.adjust(min(cols, len(items)))
    return builder.as_markup(resize_keyboard=True, input_field_placeholder=placeholder or None)

def make_keyboard_inline(items: list[tuple], cols: int = 3) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(*[InlineKeyboardButton(text=item[0], callback_data=item[0]) for item in items])
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
        await msg.answer(f'⚠ Поиск {num} картинок займет какое-то время ...', reply_markup=ReplyKeyboardRemove())
    await msg.answer(f'🔎 Ищу "{q}" в Google ({num} {inflect_num(num)}) ...', 
                            reply_markup=ReplyKeyboardRemove())
    
    await send_images(q, num, msg, state)

@dp.message(MyStates.start_state, F.text)
async def search_images_get_query(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(MyStates.search_state)
    await state.update_data({'q': message.text})
    await message.answer(f'❓ Сколько картинок найти (от 1 до {imgsearch.MAX_NUMBER})?{NL}Нажми или отправь "отмена" для отмены поиска.', 
                         reply_markup=make_keyboard_inline(list(zip(BTNS_NUMBER_IMAGES, BTNS_NUMBER_IMAGES)), 5))
    
@dp.message(MyStates.search_state, F.text.regexp(r'(\d+)|(отмена)', flags=re.I))
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

@dp.callback_query(MyStates.search_state, F.data.regexp(r'(\d+)|(отмена)', flags=re.I))
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

# ================ 3 - ПОИСК ТЕКСТА ПО КАРТИНКЕ

@dp.message(MyStates.start_state, F.photo)
async def image_get_summary(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    await state.set_state(MyStates.img_search_state)
    await message.answer(f'⌛ Подожди секуд 10-30 ...', 
                            reply_markup=ReplyKeyboardRemove())
    my_bytes_io = BytesIO()
    summary = ''
    try:
        await bot.download(message.photo[-1], destination=my_bytes_io)
        imcap = imgcap.Imgcap(my_bytes_io)
        summary = await imcap.summary(3)
    finally:
        my_bytes_io.close()

    await state.clear()
    await state.set_state(MyStates.start_state)

    if summary:
        await message.answer('. '.join(summary), reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer('🤔 Описание не найдено', reply_markup=ReplyKeyboardRemove())

# ============================================================ #

async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())