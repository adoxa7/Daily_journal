from daily_journal_bot import flask_app, run
from starlette.middleware.wsgi import WSGIMiddleware
import asyncio

asyncio.get_event_loop().create_task(run())
app = WSGIMiddleware(flask_app)
