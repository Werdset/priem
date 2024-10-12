import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.formatting import Text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager

from ql import Application, get_db  # Импортируем модели из базы данных

# Логирование
logging.basicConfig(level=logging.INFO)

# Токен вашего бота
API_TOKEN = "7506864514:AAEhAFxLmiBu9X-kkMoJMzZVe5urj0O07MQ"

# Создаем объекты бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher()

# Менеджер, который будет получать заявки (укажите его Telegram ID)
MANAGER_CHAT_ID = '1167452253'


# Состояния FSM
class ApplicationStates(StatesGroup):
    waiting_for_application = State()


# Клавиатуры
main_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Оставить заявку")]],
    resize_keyboard=True
)

status_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Принята"), KeyboardButton(text="Отклонена")]
    ],
    resize_keyboard=True
)


# Хендлер для команды /start
@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer("Добро пожаловать! Нажмите на кнопку ниже, чтобы оставить заявку.", reply_markup=main_menu)


# Хендлер для отправки заявки
@dp.message(F.text == "Оставить заявку")
async def ask_for_application(message: types.Message, state: FSMContext):
    await message.answer("Пожалуйста, введите текст вашей заявки:")
    await state.set_state(ApplicationStates.waiting_for_application)


# Хендлер для обработки заявки
@dp.message(ApplicationStates.waiting_for_application)
async def process_application(message: types.Message, state: FSMContext):
    db = next(get_db())  # Получаем сессию базы данных

    # Создаем запись заявки
    new_application = Application(user_id=message.from_user.id, text=message.text)

    try:
        db.add(new_application)
        db.commit()
        db.refresh(new_application)

        # Пересылка заявки менеджеру
        await bot.send_message(MANAGER_CHAT_ID, f"Новая заявка #{new_application.id}:\n\n{message.text}")
        await message.answer(f"Ваша заявка #{new_application.id} отправлена на рассмотрение.", reply_markup=main_menu)

    except SQLAlchemyError as e:
        db.rollback()
        await message.answer("Произошла ошибка при сохранении заявки.")

    finally:
        await state.clear()


# Хендлер для менеджера для изменения статуса заявки
@dp.message(Command("status"))
async def handle_status_change(message: types.Message):
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Используйте команду в формате: /status <номер_заявки> <Принята/Отклонена>")
        return

    try:
        application_id = int(parts[1])
        new_status = parts[2]

        db = next(get_db())  # Получаем сессию базы данных
        application = db.query(Application).filter(Application.id == application_id).first()

        if application:
            application.status = new_status
            db.commit()

            try:
                await bot.send_message(application.user_id,
                                       f"Статус вашей заявки #{application.id} изменен на '{new_status}'")
                await message.answer(f"Статус заявки #{application_id} успешно изменен.")
            except:
                await message.answer(f"Не удалось уведомить пользователя. Возможно, он заблокировал бота.")
        else:
            await message.answer(f"Заявка с номером #{application_id} не найдена.")

    except ValueError:
        await message.answer("Номер заявки должен быть числом.")
    except SQLAlchemyError:
        db.rollback()
        await message.answer("Ошибка при обновлении статуса заявки.")
    finally:
        db.close()


# Основная функция запуска бота
async def main():
    await dp.start_polling(bot, skip_updates=True)


# Запуск бота
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Exit')
