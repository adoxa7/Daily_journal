from daily_journal_bot import flask_app, run
from starlette.middleware.wsgi import WSGIMiddleware
import asyncio

# Создаем функцию для запуска в фоновом режиме
async def startup():
    # Запускаем бота в фоновом режиме
    asyncio.create_task(run())

# Запускаем функцию startup в event loop
loop = asyncio.get_event_loop()
loop.create_task(startup())

# Создаем ASGI приложение из WSGI Flask-приложения
app = WSGIMiddleware(flask_app)
