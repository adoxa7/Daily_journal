# daily_journal_bot.py

import os
import sqlite3
import datetime
import asyncio
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes,
    filters, CallbackContext
)
from apscheduler.schedulers.background import BackgroundScheduler

BOT_TOKEN = "8184049005:AAH8_1iIfLcp6htOTV-rxdQwzek3GSVwXPM"
WEBHOOK_URL = "https://daily-journal-bot.onrender.com/webhook"
DB_PATH = "journal_data.db"

flask_app = Flask(__name__)

# === DATABASE ===
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS entries (
            user_id INTEGER,
            date TEXT,
            category TEXT,
            question TEXT,
            response TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.commit()

# === SAVE ENTRY ===
def save_response(user_id, category, question, response):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO entries (user_id, date, category, question, response)
                     VALUES (?, ?, ?, ?, ?)''',
                  (user_id, datetime.date.today().isoformat(), category, question, response))
        conn.commit()

# === GLOBAL STATE ===
active_prompts = {}
app = Application.builder().token(BOT_TOKEN).build()

# === GENERIC SENDER ===
async def send_prompt(context: CallbackContext, user_id: int, category: str, prompts: list):
    active_prompts[user_id] = {"category": category, "questions": prompts.copy(), "timestamp": datetime.datetime.now()}
    for prompt in prompts:
        if isinstance(prompt[1], list):
            keyboard = [[KeyboardButton(opt) for opt in row] for row in prompt[1]]
            markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await context.bot.send_message(chat_id=user_id, text=prompt[0], reply_markup=markup)
        else:
            await context.bot.send_message(chat_id=user_id, text=prompt[0])

# === PROMPTS ===
def get_sleep_prompts():
    return [
        ("Во сколько лег спать?", None),
        ("Во сколько проснулся?", None),
        ("Как оцениваешь качество сна? (1-5)", [["5", "4", "3", "2", "1"]]),
        ("Просыпался ли ночью?", [["Да", "Нет"]]),
        ("Чувствуешь себя выспавшимся?", [["Да", "Нет"]]),
        ("Было ли пересыпание?", [["Да", "Нет"]]),
        ("Комментарий (необязательно)", None)
    ]

def get_energy_control_prompt():
    return [
        ("Соблюдал ли энергетический контроль?", [["Да", "Нет"]]),
        ("Если нет, то сколько раз произошло истощение энергии?", None)
    ]

def get_dopamine_prompts():
    return [
        ("Какими приложениями пользовался?", [["YouTube", "Instagram", "Dating Apps"]]),
        ("Сколько времени смотрел reels/shorts?", [["<30 мин", "30-60 мин", ">1 час"]]),
        ("Общее время использования смартфона?", [["<2 ч", "2-4 ч", ">4 ч"]]),
        ("Насколько хорошо контролировал импульсы? (1-5)", [["5", "4", "3", "2", "1"]])
    ]

def get_nutrition_prompts():
    return [
        ("Сколько приёмов пищи было сегодня?", [["0", "1", "2", "3", "4", "5"]]),
        ("Был ли перекус после 20:00?", [["Да", "Нет"]]),
        ("Сколько воды выпил? (в стаканах)", [["1-3", "4-6", "7+"]]),
        ("Какие БАДы принял? (можно несколько)", [["Cod liver oil", "Magnesium glycinate", "L-theanine"]]),
        ("Другие БАДы (ввести вручную, необязательно)", None)
    ]

def get_skincare_prompt():
    return [("Какой уход был сделан?", [["Ниацинамид", "Ретинол", "Пилинг", "Ничего"]])]

def get_sun_prompt():
    return [("Принимал ли солнечные лучи?", [["Да", "Нет"]]), ("Как долго?", [["<15 мин", "15-30 мин", ">30 мин"]])]

def get_work_prompt():
    return [("Сколько времени сегодня посвятил работе/обучению?", [["<1 ч", "1-2 ч", "2-4 ч", ">4 ч"]])]

# === HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Журнал активности активирован. Ожидай уведомлений в течение дня.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message.text
    if user_id in active_prompts:
        prompt_info = active_prompts[user_id]
        if prompt_info["questions"]:
            question = prompt_info["questions"].pop(0)[0]
            save_response(user_id, prompt_info["category"], question, msg)
        if not prompt_info["questions"]:
            del active_prompts[user_id]
            await update.message.reply_text("Спасибо! Все ответы сохранены ✅")

# === SCHEDULING ===
def schedule_jobs():
    scheduler = BackgroundScheduler(timezone="Asia/Almaty")

    def wrap_send(user_id, prompts, category):
        async def job():
            await send_prompt(CallbackContext.from_update(None, app), user_id, category, prompts)
        return job

    async def test_ping():
        for uid in [148797692]:
            await app.bot.send_message(chat_id=uid, text="🔁 Тест: бот работает")

    user_ids = [148797692]  # Заменить на актуальные user_id

    for uid in user_ids:
        scheduler.add_job(wrap_send(uid, get_sleep_prompts(), "Сон"), 'cron', hour=10, minute=30)
        scheduler.add_job(wrap_send(uid, get_energy_control_prompt(), "Энергетический контроль"), 'cron', hour=10, minute=35)
        scheduler.add_job(wrap_send(uid, get_sun_prompt(), "Солнце"), 'cron', hour=20)
        scheduler.add_job(wrap_send(uid, get_work_prompt(), "Работа/Обучение"), 'cron', hour=23)
        scheduler.add_job(wrap_send(uid, get_dopamine_prompts(), "Импульсивность"), 'cron', hour=23)
        scheduler.add_job(wrap_send(uid, get_nutrition_prompts(), "Питание"), 'cron', hour=23, minute=55)
        scheduler.add_job(wrap_send(uid, get_skincare_prompt(), "Уход"), 'cron', hour=0, minute=5)

        scheduler.add_job(lambda: app.bot.send_message(uid, "🌙 Время готовиться ко сну!"), 'cron', hour=1)
        scheduler.add_job(lambda: app.bot.send_message(uid, "☀️ Пора выйти на солнечный свет!"), 'cron', hour=12)
        scheduler.add_job(lambda: app.bot.send_message(uid, "🎯 Планируется 4-часовая работа или обучение."), 'cron', hour=13)

    scheduler.add_job(lambda: asyncio.create_task(test_ping()), 'interval', minutes=2)
    scheduler.start()

# === FLASK ROUTE ===
@flask_app.post("/webhook")
async def webhook():
    data = await request.get_data()
    update = Update.de_json(data.decode("utf-8"), app.bot)
    await app.update_queue.put(update)
    return "OK"

# === MAIN ===
async def run():
    init_db()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await app.initialize()
    await app.start()
    await app.bot.set_webhook(WEBHOOK_URL)
    schedule_jobs()
    print("Webhook bot is running...")
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(run())
