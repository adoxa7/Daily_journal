#!/bin/bash
gunicorn -w 1 -k uvicorn.workers.UvicornWorker wsgi:app --bind 0.0.0.0:10000
