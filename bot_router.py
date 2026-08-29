# -*- coding: utf-8 -*-
"""
Tarixdan test bot.
- O'qituvchi (admin) Mini App ichidagi Profil bo'limi orqali savollarni kiritadi.
- O'quvchilar test ishlash uchun faqat Mini App'ga yo'naltiriladi (bot ichida test yechilmaydi).
- Botning o'zi: salomlashuv, Mini App'ga taklif, reyting va shaxsiy natijalarni ko'rsatadi.

Ishga tushirish: python main.py
"""

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)

import database as db
from config import BOT_TOKEN, ADMIN_IDS, MINIAPP_URL

logging.basicConfig(level=logging.INFO)
router = Router()

TIMER_SECONDS = 15  # Mini App ichida har bir savolga beriladigan vaqt (ma'lumot uchun ko'rsatiladi)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ---------- Klaviaturalar ----------
def main_menu_kb() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🎓 Test ishlash")],
        [KeyboardButton(text="🔥 VIP obuna"), KeyboardButton(text="ℹ️ Ma'lumot va yordam")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def start_test_kb() -> InlineKeyboardMarkup:
    buttons = []
    if MINIAPP_URL:
        buttons.append(
            [InlineKeyboardButton(text="🎓 Testni boshlash", web_app=WebAppInfo(url=MINIAPP_URL))]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ================= FOYDALANUVCHI HANDLERLARI =================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    db.register_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    admin_hint = (
        "\n\n🔑 Siz adminsiz: Mini App ichidagi Profil bo'limida \"➕ Savol qo'shish\" "
        "tugmasi orqali yangi savollar kiritishingiz mumkin."
        if is_admin(message.from_user.id) else ""
    )
    await message.answer(
        f"Assalomu alaykum, {message.from_user.first_name}! 👋\n\n"
        "Bu bot orqali <b>tarix</b> fanidan test ishlashingiz mumkin.\n"
        f"Har bir savolga <b>{TIMER_SECONDS} soniya</b> vaqt beriladi!" + admin_hint,
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


@router.message(F.text == "ℹ️ Ma'lumot va yordam")
@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "🎓 <b>Test ishlash</b> — ilova orqali fanlar bo'yicha yoki aralash tarzda test ishlaysiz.\n"
        "🏆 <b>Reyting</b> — eng ko'p to'g'ri javob bergan o'quvchilar.\n"
        "📊 <b>Mening natijalarim</b> — sizning umumiy statistikangiz.\n\n"
        f"⏱ Har bir savolga {TIMER_SECONDS} soniya vaqt beriladi — ulgurmasangiz, xato hisoblanadi.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏆 Reyting", callback_data="show_top")],
                [InlineKeyboardButton(text="📊 Mening natijalarim", callback_data="my_stats")],
            ]
        ),
    )


@router.message(F.text == "🔥 VIP obuna")
async def vip_subscription(message: Message):
    # TODO: bu yerga haqiqiy VIP imkoniyatlar va to'lov havolasini qo'shing
    await message.answer(
        "🔥 <b>VIP obuna</b>\n\n"
        "Tez orada bu yerda maxsus imkoniyatlar bo'ladi: qo'shimcha mavzular, "
        "reklamasiz test va boshqa bonuslar.\n\n"
        "Hozircha bu bo'lim ishlab chiqilmoqda — tez orada e'lon qilamiz! 🚀",
        parse_mode="HTML",
    )


@router.message(F.text == "🎓 Test ishlash")
async def start_test_menu(message: Message, state: FSMContext):
    await state.clear()

    if not MINIAPP_URL:
        await message.answer(
            "⚠️ Mini App manzili hali sozlanmagan (MINIAPP_URL). "
            "Iltimos, admin bilan bog'laning."
        )
        return

    await message.answer(
        "🎓 <b>Testlarni boshlaymizmi?</b>\n\n"
        "Quyidagi tugmani bosing — ilova ochiladi va Telegram orqali "
        "parolsiz, avtomatik kirasiz.\n\n"
        "📚 Fanlar bo'yicha testlar\n"
        "🏆 Mavsum musobaqalari va reyting\n"
        "🔥 Kunlik seriya va yutuqlar\n\n"
        "👇 Bir bosishda boshlang",
        parse_mode="HTML",
        reply_markup=start_test_kb(),
    )


@router.callback_query(F.data == "show_top")
async def show_top_callback(callback: CallbackQuery):
    await send_top(callback.message, callback.from_user.id)
    await callback.answer()


@router.message(F.text == "🏆 Reyting")
async def show_top_message(message: Message):
    await send_top(message, message.from_user.id)


async def send_top(message: Message, requester_id: int):
    top = db.get_top(3)
    if not top:
        await message.answer("Hozircha hech kim test ishlamagan. Birinchi bo'ling! 🚀")
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>TOP-3 reyting</b>\n"]
    for i, user in enumerate(top):
        name = user["full_name"] or "Foydalanuvchi"
        lines.append(
            f"{medals[i]} {name} — ✅ {user['total_correct']} | ❌ {user['total_wrong']} | 🧪 {user['total_tests']} test"
        )

    rank, total_players = db.get_user_rank(requester_id)
    if rank:
        lines.append(f"\nSizning o'rningiz: <b>{rank}</b> / {total_players}")

    await message.answer("\n".join(lines), parse_mode="HTML")


async def my_stats(message: Message, user_id: int | None = None):
    uid = user_id if user_id is not None else message.from_user.id
    stats = db.get_user_stats(uid)
    if not stats or stats["total_tests"] == 0:
        await message.answer("Siz hali birorta test ishlamagansiz. \"🎓 Test ishlash\" tugmasini bosing!")
        return

    total = stats["total_correct"] + stats["total_wrong"]
    percent = round(stats["total_correct"] / total * 100) if total else 0
    rank, total_players = db.get_user_rank(uid)

    await message.answer(
        f"📊 <b>Sizning natijalaringiz</b>\n\n"
        f"✅ To'g'ri javoblar: <b>{stats['total_correct']}</b>\n"
        f"❌ Xato javoblar: <b>{stats['total_wrong']}</b>\n"
        f"🧪 Jami testlar: {stats['total_tests']}\n"
        f"🎯 Umumiy aniqlik: <b>{percent}%</b>\n"
        f"🏆 Reytingdagi o'rningiz: <b>{rank}</b> / {total_players}",
        parse_mode="HTML",
    )


@router.message(F.text == "📊 Mening natijalarim")
async def my_stats_message(message: Message):
    await my_stats(message)


@router.callback_query(F.data == "my_stats")
async def my_stats_callback(callback: CallbackQuery):
    await my_stats(callback.message, user_id=callback.from_user.id)
    await callback.answer()


# ================= ADMIN: YORDAMCHI BUYRUQLAR =================
# (Savol qo'shishning o'zi endi faqat Mini App ichida — Profil bo'limida.
#  Bu ikkita buyruq esa bot orqali tezkor tekshirish/o'chirish uchun qoldirilgan.)

@router.message(Command("savollar_soni"))
async def admin_question_count(message: Message):
    if not is_admin(message.from_user.id):
        return
    total = db.get_question_count()
    lines = [f"📊 Jami savollar: <b>{total}</b>\n"]
    for c in db.get_classes():
        for s in db.get_subjects(c):
            cnt = db.get_question_count(class_num=c, subject=s)
            lines.append(f"  {c}-sinf — {s}: {cnt} ta")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("oxirgisini_ochir"))
async def admin_delete_last(message: Message):
    if not is_admin(message.from_user.id):
        return
    ok = db.delete_last_question(message.from_user.id)
    if ok:
        await message.answer("🗑 Oxirgi qo'shgan savolingiz o'chirildi.")
    else:
        await message.answer("Siz hali savol qo'shmagansiz.")


@router.message(Command("bekor"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_kb())


# Bu modul faqat `router`ni tayyorlaydi. Botni ishga tushirish uchun main.py'ga qarang.
