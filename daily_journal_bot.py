# daily_journal_bot.py

import os
import sqlite3
import datetime
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, CallbackContext
)
from apscheduler.schedulers.background import BackgroundScheduler

BOT_TOKEN = os.getenv("BOT_TOKEN") or "PASTE_YOUR_BOT_TOKEN_HERE"
DB_PATH = "journal_data.db"

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

# === GLOBAL TRACKING OF ACTIVE PROMPTS ===
active_prompts = {}

# === GENERIC SENDER ===
async def send_prompt(context: CallbackContext, user_id: int, category: str, prompts: list):
    active_prompts[user_id] = {"category": category, "questions": prompts.copy(), "timestamp": datetime.datetime.now()}
    for prompt in prompts:
        if isinstance(prompt[1], list):  # multiple choice
            keyboard = [[KeyboardButton(opt) for opt in row] for row in prompt[1]]
            markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await context.bot.send_message(chat_id=user_id, text=prompt[0], reply_markup=markup)
        else:
            await context.bot.send_message(chat_id=user_id, text=prompt[0])

# === INDIVIDUAL PROMPTS ===
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
def schedule_jobs(app: Application):
    scheduler = BackgroundScheduler(timezone="Asia/Almaty")

    def wrap_send(user_id, prompts, category):
        async def job():
            await send_prompt(app.bot, user_id, category, prompts)
        return job

    user_ids = [123456789]  # замените на свой ID или список ID пользователей

    for uid in user_ids:
        scheduler.add_job(wrap_send(uid, get_sleep_prompts(), "Сон"), 'cron', hour=10, minute=30)
        scheduler.add_job(wrap_send(uid, get_energy_control_prompt(), "Энергетический контроль"), 'cron', hour=10, minute=35)
        scheduler.add_job(wrap_send(uid, get_sun_prompt(), "Солнце"), 'cron', hour=20)
        scheduler.add_job(wrap_send(uid, get_work_prompt(), "Работа/Обучение"), 'cron', hour=23)
        scheduler.add_job(wrap_send(uid, get_dopamine_prompts(), "Импульсивность"), 'cron', hour=23)
        scheduler.add_job(wrap_send(uid, get_nutrition_prompts(), "Питание"), 'cron', hour=23, minute=55)
        scheduler.add_job(wrap_send(uid, get_skincare_prompt(), "Уход"), 'cron', hour=0, minute=5)

        scheduler.add_job(lambda: app.bot.send_message(uid, "🌙 Время готовиться ко сну: выключи свет, убери гаджеты, позволь мозгу отдохнуть. Завтрашний ты скажет спасибо!"), 'cron', hour=1)
        scheduler.add_job(lambda: app.bot.send_message(uid, "☀️ Пора выйти на солнечный свет!"), 'cron', hour=12)
        scheduler.add_job(lambda: app.bot.send_message(uid, "🎯 Планируется 4-часовая работа или обучение. Будь продуктивен!"), 'cron', hour=13)

    scheduler.start()

# === MAIN ===
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    schedule_jobs(app)
    print("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()

