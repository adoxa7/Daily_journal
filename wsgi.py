import asyncio
from daily_journal_bot import flask_app, run

asyncio.create_task(run())  # запуск бота параллельно Flask
app = flask_app
