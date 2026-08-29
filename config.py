# -*- coding: utf-8 -*-
"""
Bot va Mini App sozlamalari.

BOT_TOKEN: @BotFather orqali olasiz (/newbot).
ADMIN_IDS: savol qo'sha oladigan Telegram user_id'lar (@userinfobot orqali ID'ingizni bilib oling).
MINIAPP_URL: Mini App joylashgan HTTPS manzil. Deploy qilgandan keyin (masalan Railway sizga
             https://tarix-bot-production.up.railway.app kabi manzil beradi) shu yerga yozasiz.
             Bo'sh qoldirsangiz, botdagi "🎮 Mini ilovani ochish" tugmasi chiqmaydi — bot oddiy
             rejimda ishlayveradi.
PORT: web-server qaysi portda ishlashi (hosting xizmati odatda buni avtomatik beradi).
"""

import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "8961799336:AAHb7eIMGW6LvTg1FliHmeZMC052WUhsVCY")

ADMIN_IDS = [
    8724919729  # <-- shu yerga o'zingizning Telegram ID'ingizni yozing (@userinfobot dan oling)
]

MINIAPP_URL = os.getenv("MINIAPP_URL", "")  # masalan: "https://sizning-domeningiz.up.railway.app"

PORT = int(os.getenv("PORT", "8000"))
