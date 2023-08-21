import logging
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
# from aiogram.utils import markdown as md
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message, BufferedInputFile, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.chat_action import ChatActionMiddleware, ChatActionSender

from config import CONFIG
import imgsearch

# ============================================================ #

BOT_HELP = \
"""
Отправь описание картинки, например "жёлтый экскаватор", бот вернёт картинки (от 1 до 50). 
Отправь боту картинку, бот вернёт её описание.
"""

BTNS_NUMBER_IMAGES = ['1', '5', '10', '20', '40', '50']

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
                logging.exception(err)
                await message.answer(f'😩 Ошибка обработки изображения', reply_markup=reply_markup)
                continue
    else:
        await message.answer('🤔 Картинки не найдены', reply_markup=ReplyKeyboardRemove())
    await state.clear()
    await state.set_state(MyStates.start_state)

@dp.message(MyStates.start_state, F.text)
async def search_images_get_query(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(MyStates.search_state)
    await state.update_data({'q': message.text})
    await message.answer(f'❓ Сколько картинок найти (от 1 до {imgsearch.MAX_NUMBER})?', 
                         reply_markup=make_keyboard(BTNS_NUMBER_IMAGES))
    
@dp.message(MyStates.search_state, F.text.regexp(r'\d+'))
async def search_images_process_query(message: Message, state: FSMContext, bot: Bot):    
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id, interval=2.0):
        data = await state.get_data()
        if not 'q' in data:
            await state.clear()
            await state.set_state(MyStates.start_state)
            await message.answer('⛔ Не указана ключевая фраза для поиска', 
                                reply_markup=ReplyKeyboardRemove())
            return

        q = data['q']
        num = int(message.text)
        if num > imgsearch.MAX_NUMBER:
            await message.answer(f'⚠ Будет показано не более {imgsearch.MAX_NUMBER} картинок', reply_markup=ReplyKeyboardRemove())
        if num > 14:
            await message.answer(f'⚠ Поиск {num} картинок займет какое-то время ...', reply_markup=ReplyKeyboardRemove())
        await message.answer(f'🔎 Ищу "{q}" в Google ({num} картинок) ...', 
                                reply_markup=ReplyKeyboardRemove())
        await send_images(q, int(message.text), message, state)

# ================ 3 - ПОИСК ТЕКСТА ПО КАРТИНКЕ

@dp.message(MyStates.start_state, F.photo)
async def search_txt_by_image(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(MyStates.search_state)
    await state.update_data({'q': message.text})
    await message.answer('❓ Сколько картинок найти?', 
                         reply_markup=make_keyboard(BTNS_NUMBER_IMAGES))

# ============================================================ #

async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())