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

BOT_TOKEN = os.getenv("BOT_TOKEN") or "PASTE_YOUR_BOT_TOKEN_HERE"
WEBHOOK_URL = os.getenv("WEBHOOK_URL") or "https://your-app-name.onrender.com/webhook"
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
# ... [оставляем все функции get_sleep_prompts() и т.п. без изменений] ...

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
