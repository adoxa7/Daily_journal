from daily_journal_bot import flask_app, run
import asyncio

asyncio.get_event_loop().create_task(run())  # корректный запуск фоновой задачи

app = flask_app
