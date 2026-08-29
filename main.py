# -*- coding: utf-8 -*-
"""
Bitta dasturda ikkalasini birga ishga tushiradi:
  1) Telegram bot (aiogram, polling rejimida)
  2) Mini App web-server (FastAPI + uvicorn)

Ishga tushirish: python main.py
"""

import asyncio
import logging

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import database as db
from config import BOT_TOKEN, PORT
from bot_router import router
from webapp import app as fastapi_app

logging.basicConfig(level=logging.INFO)


async def run_bot():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    logging.info("Telegram bot ishga tushdi (polling)...")
    await dp.start_polling(bot)


async def run_webserver():
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    logging.info(f"Mini App server {PORT}-portda ishga tushdi...")
    await server.serve()


async def main():
    db.init_db()
    await asyncio.gather(run_bot(), run_webserver())


if __name__ == "__main__":
    asyncio.run(main())
