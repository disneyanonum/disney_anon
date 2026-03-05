
import asyncio
import datetime
import logging
import sqlite3
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

import matplotlib.pyplot as plt

TOKEN = "8639786947:AAGWLS6SIrBvhz7dAIHL64Y31XXyKyICz3c"

logging.basicConfig(level=logging.INFO)

bot = Bot(TOKEN)
dp = Dispatcher()

# ---------- DATABASE ----------
db = sqlite3.connect("disney_anon.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS stats(
user_id INTEGER PRIMARY KEY,
messages INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS activity(
date TEXT PRIMARY KEY,
count INTEGER
)
""")

db.commit()
# ---------------------------------

waiting_users = {}
reply_users = {}

menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔗 Моя ссылка")],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🏆 Топ")],
        [KeyboardButton(text="📈 График"), KeyboardButton(text="ℹ️ Помощь")]
    ],
    resize_keyboard=True
)

def add_message(user_id):
    # Update user stats
    cursor.execute("SELECT messages FROM stats WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE stats SET messages=? WHERE user_id=?", (row[0]+1, user_id))
    else:
        cursor.execute("INSERT INTO stats(user_id,messages) VALUES(?,1)", (user_id,))

    # Update daily activity
    today = str(datetime.date.today())
    cursor.execute("SELECT count FROM activity WHERE date=?", (today,))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE activity SET count=? WHERE date=?", (row[0]+1, today))
    else:
        cursor.execute("INSERT INTO activity(date,count) VALUES(?,1)", (today,))
    db.commit()

@dp.message(CommandStart())
async def start(message: Message):
    args = message.text.split()
    if len(args) > 1:
        try:
            target = int(args[1])
        except:
            await message.answer("Ошибка ссылки")
            return
        if target == message.from_user.id:
            await message.answer("Нельзя отправить сообщение самому себе")
            return
        waiting_users[message.from_user.id] = target
        await message.answer("🎭 Disney Anon\nНапиши сообщение, фото, видео или голосовое. Оно будет отправлено анонимно.")
    else:
        await message.answer("🎭 Disney Anon\nПолучай анонимные сообщения 👇", reply_markup=menu)

@dp.message(F.text == "🔗 Моя ссылка")
async def my_link(message: Message):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={message.from_user.id}"
    await message.answer(f"🔗 Твоя ссылка:\n{link}")

@dp.message(F.text == "📊 Статистика")
async def stat(message: Message):
    cursor.execute("SELECT messages FROM stats WHERE user_id=?", (message.from_user.id,))
    row = cursor.fetchone()
    count = row[0] if row else 0
    await message.answer(f"📩 Получено сообщений: {count}")

@dp.message(F.text == "🏆 Топ")
async def top(message: Message):
    cursor.execute("SELECT user_id,messages FROM stats ORDER BY messages DESC LIMIT 10")
    rows = cursor.fetchall()
    if not rows:
        await message.answer("Пока нет статистики")
        return
    text = "🏆 Топ пользователей\n\n"
    place = 1
    for uid, count in rows:
        try:
            user = await bot.get_chat(uid)
            name = user.first_name
        except:
            name = "Пользователь"
        text += f"{place}. {name} — {count}\n"
        place += 1
    await message.answer(text)

@dp.message(F.text == "📈 График")
async def graph(message: Message):
    cursor.execute("SELECT date,count FROM activity ORDER BY date")
    rows = cursor.fetchall()
    if not rows:
        await message.answer("Пока нет данных активности")
        return
    dates = [r[0] for r in rows]
    values = [r[1] for r in rows]
    plt.figure()
    plt.plot(dates, values)
    plt.xlabel("Дата")
    plt.ylabel("Сообщения")
    file = "activity.png"
    plt.savefig(file)
    plt.close()
    await message.answer_photo(photo=open(file, "rb"), caption="📈 График активности")

@dp.message(F.text == "ℹ️ Помощь")
async def help_command(message: Message):
    await message.answer("ℹ️ Как пользоваться ботом\n1️⃣ Нажми 'Моя ссылка'\n2️⃣ Отправь её друзьям\n3️⃣ Получай анонимные сообщения")

@dp.message(F.content_type.in_({"text","photo","video","voice"}))
async def anon(message: Message):
    uid = message.from_user.id
    if uid not in waiting_users:
        return
    target = waiting_users[uid]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_{uid}")]])
    if message.text:
        await bot.send_message(target, f"📩 Анонимное сообщение\n\n{message.text}", reply_markup=keyboard)
    elif message.photo:
        await bot.send_photo(target, message.photo[-1].file_id, caption="📸 Анонимное фото", reply_markup=keyboard)
    elif message.video:
        await bot.send_video(target, message.video.file_id, caption="🎥 Анонимное видео", reply_markup=keyboard)
    elif message.voice:
        await bot.send_voice(target, message.voice.file_id, reply_markup=keyboard)
    add_message(target)
    await message.answer("✅ Сообщение отправлено")
    del waiting_users[uid]

@dp.callback_query(F.data.startswith("reply_"))
async def reply_button(call: CallbackQuery):
    sender = int(call.data.split("_")[1])
    reply_users[call.from_user.id] = sender
    await call.message.answer("💬 Напиши ответ на сообщение")

@dp.message()
async def reply_message(message: Message):
    uid = message.from_user.id
    if uid not in reply_users:
        return
    target = reply_users[uid]
    await bot.send_message(target, f"💬 Ответ на твоё сообщение\n\n{message.text}")
    await message.answer("✅ Ответ успешно отправлен")
    del reply_users[uid]

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
