# -*- coding: utf-8 -*-
"""
Tarixdan test bot.
- O'qituvchi (admin) botning o'zida savollarni kiritadi (baza oldindan yo'q, quiz-bot uslubida).
- O'quvchilar sinf / mavzu / aralash tarzda test ishlaydi.
- Har bir savolga 15 soniya vaqt beriladi — vaqt tugasa avtomatik xato hisoblanib, keyingi savolga o'tiladi.
- Har o'quvchining to'g'ri/xato natijalari saqlanadi, umumiy TOP-3 reyting mavjud.

Ishga tushirish: python bot.py
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
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

QUESTIONS_PER_TEST = 10   # bitta testda nechta savol beriladi (mavjud bo'lsa)
TIMER_SECONDS = 15        # har bir savolga beriladigan vaqt

# Har foydalanuvchi uchun faol "vaqt tugadi" tayrnerini saqlaymiz (bekor qilish uchun)
pending_timers: dict[int, asyncio.Task] = {}


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def cancel_timer(user_id: int):
    task = pending_timers.pop(user_id, None)
    if task and not task.done():
        task.cancel()


# ---------- Holatlar (FSM) ----------
class TestFlow(StatesGroup):
    choosing_mode = State()
    choosing_class = State()
    choosing_subject = State()
    choosing_topic = State()
    in_test = State()


class AdminAddFlow(StatesGroup):
    choosing_class = State()
    choosing_subject = State()
    entering_topic = State()
    entering_question = State()
    entering_options = State()
    choosing_correct = State()
    ask_continue = State()


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


def mode_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📚 Sinf bo'yicha", callback_data="mode:class")],
            [InlineKeyboardButton(text="📖 Mavzu bo'yicha", callback_data="mode:topic")],
            [InlineKeyboardButton(text="🔀 Aralash test", callback_data="mode:mixed")],
        ]
    )


def classes_kb(prefix: str = "class") -> InlineKeyboardMarkup:
    classes = db.get_classes()
    buttons = [InlineKeyboardButton(text=f"{c}-sinf", callback_data=f"{prefix}:{c}") for c in classes]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back:mode")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subjects_kb(class_num: int, prefix: str = "subj") -> InlineKeyboardMarkup:
    subjects = db.get_subjects(class_num)
    rows = [[InlineKeyboardButton(text=s, callback_data=f"{prefix}:{i}")] for i, s in enumerate(subjects)]
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back:class")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def topics_kb(class_num: int, subject: str) -> InlineKeyboardMarkup:
    topics = db.get_topics(class_num, subject)
    rows = [[InlineKeyboardButton(text=t, callback_data=f"topic:{i}")] for i, t in enumerate(topics)]
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back:subject")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def question_kb(options: list[str]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=opt, callback_data=f"ans:{i}")] for i, opt in enumerate(options)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def after_test_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔁 Yana test", callback_data="restart")],
            [InlineKeyboardButton(text="🏆 Reytingni ko'rish", callback_data="show_top")],
        ]
    )


def yes_no_kb(yes_data: str, no_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Ha", callback_data=yes_data),
             InlineKeyboardButton(text="❌ Yo'q", callback_data=no_data)],
        ]
    )


# ---------- Test jarayoni yordamchi funksiyalari ----------
import random


def prepare_test(questions: list[dict]) -> list[dict]:
    pool = questions.copy()
    random.shuffle(pool)
    chosen = pool[:QUESTIONS_PER_TEST] if len(pool) > QUESTIONS_PER_TEST else pool
    prepared = []
    for q in chosen:
        opts = q["options"].copy()
        random.shuffle(opts)
        prepared.append({"q": q["q"], "options": opts, "correct": q["correct"]})
    return prepared


async def send_question(bot: Bot, chat_id: int, user_id: int, state: FSMContext):
    data = await state.get_data()
    idx = data["index"]
    test_questions = data["questions"]
    q = test_questions[idx]
    text = f"❓ Savol {idx + 1}/{len(test_questions)}  ⏱ {TIMER_SECONDS} soniya\n\n{q['q']}"
    sent = await bot.send_message(chat_id, text, reply_markup=question_kb(q["options"]))
    await state.update_data(current_message_id=sent.message_id)

    cancel_timer(user_id)
    task = asyncio.create_task(question_timeout(bot, chat_id, user_id, state, idx))
    pending_timers[user_id] = task


async def question_timeout(bot: Bot, chat_id: int, user_id: int, state: FSMContext, expected_index: int):
    try:
        await asyncio.sleep(TIMER_SECONDS)
    except asyncio.CancelledError:
        return

    current_state = await state.get_state()
    if current_state != TestFlow.in_test.state:
        return
    data = await state.get_data()
    if not data or data.get("index") != expected_index:
        return  # foydalanuvchi allaqachon javob bergan / holat o'zgargan

    test_questions = data["questions"]
    q = test_questions[expected_index]
    message_id = data.get("current_message_id")

    await state.update_data(wrong=data["wrong"] + 1, index=expected_index + 1)

    try:
        await bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=f"⏰ Vaqt tugadi! To'g'ri javob: {q['correct']}",
        )
    except Exception:
        pass

    new_data = await state.get_data()
    if new_data["index"] >= len(test_questions):
        await finish_test(bot, chat_id, user_id, state)
    else:
        await send_question(bot, chat_id, user_id, state)


async def finish_test(bot: Bot, chat_id: int, user_id: int, state: FSMContext):
    cancel_timer(user_id)
    data = await state.get_data()
    correct = data["correct"]
    wrong = data["wrong"]
    total = correct + wrong
    percent = round(correct / total * 100) if total else 0

    db.save_attempt(
        user_id=user_id,
        mode=data.get("mode"),
        class_num=data.get("class_num"),
        subject=data.get("subject"),
        topic=data.get("topic"),
        correct=correct,
        wrong=wrong,
        total=total,
    )

    await bot.send_message(
        chat_id,
        f"🏁 <b>Test yakunlandi!</b>\n\n"
        f"✅ To'g'ri javoblar: <b>{correct}</b>\n"
        f"❌ Xato javoblar: <b>{wrong}</b>\n"
        f"📊 Jami savollar: {total}\n"
        f"🎯 Natija: <b>{percent}%</b>\n\n"
        f"Davom etasizmi?",
        reply_markup=after_test_kb(),
        parse_mode="HTML",
    )
    await state.clear()


# ================= FOYDALANUVCHI HANDLERLARI =================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    db.register_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    admin_hint = "\n\n🔑 Siz adminsiz: /savol_qoshish orqali yangi savollar kiritishingiz mumkin." if is_admin(message.from_user.id) else ""
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
        # MINIAPP_URL sozlanmagan bo'lsa, botning eski ichki test rejimiga tushamiz
        if db.get_question_count() == 0:
            await message.answer("Hozircha bazada birorta ham savol yo'q. O'qituvchi savol kiritishini kuting. 🙏")
            return
        await state.set_state(TestFlow.choosing_mode)
        await message.answer("Test turini tanlang 👇", reply_markup=mode_kb())
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


@router.callback_query(F.data == "restart")
async def restart_test(callback: CallbackQuery, state: FSMContext):
    if db.get_question_count() == 0:
        await callback.message.answer("Hozircha bazada birorta ham savol yo'q.")
        await callback.answer()
        return
    await state.set_state(TestFlow.choosing_mode)
    await callback.message.answer("Test turini tanlang 👇", reply_markup=mode_kb())
    await callback.answer()


@router.callback_query(F.data == "back:mode")
async def back_to_mode(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TestFlow.choosing_mode)
    await callback.message.edit_text("Test turini tanlang 👇", reply_markup=mode_kb())
    await callback.answer()


@router.callback_query(F.data == "back:class")
async def back_to_class(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TestFlow.choosing_class)
    await callback.message.edit_text("Sinfni tanlang 👇", reply_markup=classes_kb())
    await callback.answer()


@router.callback_query(F.data == "back:subject")
async def back_to_subject(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.set_state(TestFlow.choosing_subject)
    await callback.message.edit_text(
        f"{data['class_num']}-sinf uchun fanni tanlang 👇", reply_markup=subjects_kb(data["class_num"])
    )
    await callback.answer()


@router.callback_query(TestFlow.choosing_mode, F.data.startswith("mode:"))
async def choose_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split(":")[1]
    await state.update_data(mode=mode)

    if mode == "mixed":
        all_qs = db.get_all_questions()
        prepared = prepare_test(all_qs)
        await state.update_data(questions=prepared, index=0, correct=0, wrong=0,
                                 class_num=None, subject="Aralash", topic="Aralash")
        await state.set_state(TestFlow.in_test)
        await callback.message.edit_text(f"🔀 Aralash test boshlandi! Jami {len(prepared)} ta savol.\nOmad! 🍀")
        await send_question(callback.bot, callback.message.chat.id, callback.from_user.id, state)
    else:
        await state.set_state(TestFlow.choosing_class)
        await callback.message.edit_text("Sinfni tanlang 👇", reply_markup=classes_kb())
    await callback.answer()


@router.callback_query(TestFlow.choosing_class, F.data.startswith("class:"))
async def choose_class(callback: CallbackQuery, state: FSMContext):
    class_num = int(callback.data.split(":")[1])
    await state.update_data(class_num=class_num)
    await state.set_state(TestFlow.choosing_subject)
    await callback.message.edit_text(
        f"{class_num}-sinf uchun fanni tanlang 👇", reply_markup=subjects_kb(class_num)
    )
    await callback.answer()


@router.callback_query(TestFlow.choosing_subject, F.data.startswith("subj:"))
async def choose_subject(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    class_num = data["class_num"]
    subject = db.get_subjects(class_num)[idx]
    await state.update_data(subject=subject)

    if data["mode"] == "class":
        qs = db.get_questions_by_subject(class_num, subject)
        prepared = prepare_test(qs)
        await state.update_data(questions=prepared, index=0, correct=0, wrong=0, topic="Barcha mavzular")
        await state.set_state(TestFlow.in_test)
        await callback.message.edit_text(
            f"📚 {class_num}-sinf — {subject} testi boshlandi! Jami {len(prepared)} ta savol.\nOmad! 🍀"
        )
        await send_question(callback.bot, callback.message.chat.id, callback.from_user.id, state)
    else:  # mode == topic
        await state.set_state(TestFlow.choosing_topic)
        await callback.message.edit_text(
            f"{class_num}-sinf — {subject}: mavzuni tanlang 👇", reply_markup=topics_kb(class_num, subject)
        )
    await callback.answer()


@router.callback_query(TestFlow.choosing_topic, F.data.startswith("topic:"))
async def choose_topic(callback: CallbackQuery, state: FSMContext):
    topic_idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    class_num = data["class_num"]
    subject = data["subject"]
    topic = db.get_topics(class_num, subject)[topic_idx]

    qs = db.get_questions_by_topic(class_num, subject, topic)
    prepared = prepare_test(qs)
    await state.update_data(questions=prepared, index=0, correct=0, wrong=0, topic=topic)
    await state.set_state(TestFlow.in_test)
    await callback.message.edit_text(
        f"📖 {class_num}-sinf — {subject} — «{topic}»\nJami {len(prepared)} ta savol.\nOmad! 🍀"
    )
    await send_question(callback.bot, callback.message.chat.id, callback.from_user.id, state)
    await callback.answer()


@router.callback_query(TestFlow.in_test, F.data.startswith("ans:"))
async def answer_question(callback: CallbackQuery, state: FSMContext):
    cancel_timer(callback.from_user.id)

    data = await state.get_data()
    idx = data["index"]
    test_questions = data["questions"]
    q = test_questions[idx]

    chosen_idx = int(callback.data.split(":")[1])
    chosen_text = q["options"][chosen_idx]
    is_correct = chosen_text == q["correct"]

    if is_correct:
        await state.update_data(correct=data["correct"] + 1)
        await callback.answer("✅ To'g'ri!", show_alert=False)
    else:
        await state.update_data(wrong=data["wrong"] + 1)
        await callback.answer(f"❌ Xato! To'g'ri javob: {q['correct']}", show_alert=True)

    next_index = idx + 1
    await state.update_data(index=next_index)

    if next_index >= len(test_questions):
        await callback.message.delete()
        await finish_test(callback.bot, callback.message.chat.id, callback.from_user.id, state)
    else:
        await callback.message.delete()
        await send_question(callback.bot, callback.message.chat.id, callback.from_user.id, state)


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


# ================= ADMIN: SAVOL QO'SHISH =================

@router.message(Command("savol_qoshish"))
async def admin_add_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Kechirasiz, savol qo'shish faqat adminlar uchun.")
        return
    await state.clear()
    await state.set_state(AdminAddFlow.choosing_class)
    await message.answer(
        "➕ <b>Yangi savol qo'shish</b>\n\nAvval sinfni tanlang (yoki yangi sinf raqamini yozing, masalan: 9):",
        parse_mode="HTML",
        reply_markup=admin_classes_kb(),
    )


def admin_classes_kb() -> InlineKeyboardMarkup:
    existing = db.get_classes()
    all_classes = sorted(set(existing) | set(range(5, 12)))
    buttons = [InlineKeyboardButton(text=f"{c}-sinf", callback_data=f"aclass:{c}") for c in all_classes]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(AdminAddFlow.choosing_class, F.data.startswith("aclass:"))
async def admin_choose_class(callback: CallbackQuery, state: FSMContext):
    class_num = int(callback.data.split(":")[1])
    await state.update_data(class_num=class_num)
    await state.set_state(AdminAddFlow.choosing_subject)
    await callback.message.edit_text(
        f"{class_num}-sinf tanlandi.\n\nEndi fanni tanlang:",
        reply_markup=admin_subjects_kb(),
    )
    await callback.answer()


@router.message(AdminAddFlow.choosing_class)
async def admin_choose_class_text(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("Iltimos, sinf raqamini kiriting (masalan: 9) yoki yuqoridagi tugmalardan tanlang.")
        return
    class_num = int(message.text.strip())
    await state.update_data(class_num=class_num)
    await state.set_state(AdminAddFlow.choosing_subject)
    await message.answer(f"{class_num}-sinf tanlandi.\n\nEndi fanni tanlang:", reply_markup=admin_subjects_kb())


def admin_subjects_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏛 O'zbekiston tarixi", callback_data="asubj:O'zbekiston tarixi")],
            [InlineKeyboardButton(text="🌍 Jahon tarixi", callback_data="asubj:Jahon tarixi")],
        ]
    )


@router.callback_query(AdminAddFlow.choosing_subject, F.data.startswith("asubj:"))
async def admin_choose_subject(callback: CallbackQuery, state: FSMContext):
    subject = callback.data.split(":", 1)[1]
    await state.update_data(subject=subject)
    await state.set_state(AdminAddFlow.entering_topic)
    await callback.message.edit_text(
        f"Fan: {subject}\n\nEndi mavzu nomini yozing (masalan: «Amir Temur va Temuriylar davri»):"
    )
    await callback.answer()


@router.message(AdminAddFlow.entering_topic)
async def admin_enter_topic(message: Message, state: FSMContext):
    topic = message.text.strip()
    await state.update_data(topic=topic)
    await state.set_state(AdminAddFlow.entering_question)
    await message.answer(
        f"Mavzu: «{topic}»\n\n✍️ Endi <b>savol matnini</b> yuboring:",
        parse_mode="HTML",
    )


@router.message(AdminAddFlow.entering_question)
async def admin_enter_question(message: Message, state: FSMContext):
    await state.update_data(question_text=message.text.strip())
    await state.set_state(AdminAddFlow.entering_options)
    await message.answer(
        "Endi <b>4 ta javob variantini</b> har birini alohida qatorda yuboring.\n\n"
        "Namuna:\n<code>Amir Temur\nMirzo Ulug'bek\nShayboniyxon\nAbdullaxon II</code>\n\n"
        "(Birinchi qator to'g'ri javob bo'lishi shart emas — keyingi qadamda to'g'risini o'zingiz tanlaysiz)",
        parse_mode="HTML",
    )


@router.message(AdminAddFlow.entering_options)
async def admin_enter_options(message: Message, state: FSMContext):
    lines = [line.strip() for line in message.text.split("\n") if line.strip()]
    if len(lines) != 4:
        await message.answer(
            f"❗️ Aniq <b>4 ta</b> variant kerak, siz {len(lines)} ta qator yubordingiz. "
            "Har birini alohida qatorda qayta yuboring.",
            parse_mode="HTML",
        )
        return

    await state.update_data(options=lines)
    await state.set_state(AdminAddFlow.choosing_correct)
    rows = [[InlineKeyboardButton(text=opt, callback_data=f"correct:{i}")] for i, opt in enumerate(lines)]
    await message.answer(
        "✅ Qaysi variant <b>to'g'ri javob</b>?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(AdminAddFlow.choosing_correct, F.data.startswith("correct:"))
async def admin_choose_correct(callback: CallbackQuery, state: FSMContext):
    correct_idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    options = data["options"]
    correct_text = options[correct_idx]

    db.add_question(
        class_num=data["class_num"],
        subject=data["subject"],
        topic=data["topic"],
        question=data["question_text"],
        options=options,
        correct=correct_text,
        added_by=callback.from_user.id,
    )

    await callback.message.edit_text(
        f"✅ Savol saqlandi!\n\n"
        f"📚 {data['class_num']}-sinf — {data['subject']} — «{data['topic']}»\n"
        f"❓ {data['question_text']}\n"
        f"✅ To'g'ri javob: {correct_text}"
    )
    await state.set_state(AdminAddFlow.ask_continue)
    await callback.message.answer(
        "Yana shu mavzuga savol qo'shasizmi?",
        reply_markup=yes_no_kb("cont:same", "cont:new"),
    )
    await callback.answer()


@router.callback_query(AdminAddFlow.ask_continue, F.data == "cont:same")
async def admin_continue_same(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminAddFlow.entering_question)
    await callback.message.edit_text("✍️ Keyingi savol matnini yuboring:")
    await callback.answer()


@router.callback_query(AdminAddFlow.ask_continue, F.data == "cont:new")
async def admin_continue_new(callback: CallbackQuery, state: FSMContext):
    total = db.get_question_count()
    await callback.message.edit_text(
        f"👍 Bo'ldi! Hozircha bazada jami <b>{total}</b> ta savol bor.\n\n"
        "Yangi savol qo'shish uchun /savol_qoshish, testni sinash uchun \"📝 Test boshlash\" tugmasini bosing.",
        parse_mode="HTML",
    )
    await state.clear()
    await callback.answer()


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
    cancel_timer(message.from_user.id)
    await message.answer("Bekor qilindi.", reply_markup=main_menu_kb())


# Bu modul faqat `router`ni tayyorlaydi. Botni ishga tushirish uchun main.py'ga qarang.
