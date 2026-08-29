# -*- coding: utf-8 -*-
"""
Mini App backend (FastAPI).
Statik fayllarni (index.html/style.css/app.js) va API endpointlarini beradi.
Har bir so'rov Telegram WebApp `initData` orqali autentifikatsiya qilinadi.
"""

import random
import uuid
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database as db
from auth import validate_init_data
from config import BOT_TOKEN

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Tarix Test Mini App")


@app.on_event("startup")
def _on_startup():
    # main.py orqali ishga tushirilganda ham, "uvicorn webapp:app" bilan
    # to'g'ridan-to'g'ri ishga tushirilganda ham jadvallar mavjudligini kafolatlaydi.
    db.init_db()


# Test sessiyalari xotirada saqlanadi: {session_id: {"user_id":.., "questions":[...], "index":0, "correct":0, "wrong":0, ...}}
SESSIONS: dict[str, dict] = {}

QUESTIONS_PER_TEST = 10


def get_user_from_header(x_init_data: str | None) -> dict:
    result = validate_init_data(x_init_data or "", BOT_TOKEN)
    if not result or not result.get("user"):
        raise HTTPException(status_code=401, detail="Avtorizatsiya muvaffaqiyatsiz. Ilovani Telegram orqali oching.")
    return result["user"]


def ensure_user(tg_user: dict):
    full_name = " ".join(filter(None, [tg_user.get("first_name"), tg_user.get("last_name")])) or "Foydalanuvchi"
    db.register_user(tg_user["id"], full_name, tg_user.get("username"))


# ---------- Pydantic modellar ----------
class TestStartRequest(BaseModel):
    mode: str            # "class" | "topic" | "mixed"
    class_num: int | None = None
    subject: str | None = None
    topic: str | None = None


class AnswerRequest(BaseModel):
    session_id: str
    question_index: int
    chosen_index: int | None = None  # None => vaqt tugadi (timeout)


class FinishRequest(BaseModel):
    session_id: str


# ---------- Foydalanuvchi / profil ----------
@app.get("/api/me")
def api_me(x_init_data: str | None = Header(default=None)):
    tg_user = get_user_from_header(x_init_data)
    ensure_user(tg_user)
    stats = db.get_user_stats(tg_user["id"]) or {
        "total_correct": 0, "total_wrong": 0, "total_tests": 0
    }
    rank, total_players = db.get_user_rank(tg_user["id"])
    total = stats["total_correct"] + stats["total_wrong"]
    accuracy = round(stats["total_correct"] / total * 100) if total else 0
    level = 1 + stats["total_correct"] // 15

    return {
        "id": tg_user["id"],
        "first_name": tg_user.get("first_name", "Foydalanuvchi"),
        "photo_url": tg_user.get("photo_url"),
        "total_correct": stats["total_correct"],
        "total_wrong": stats["total_wrong"],
        "total_tests": stats["total_tests"],
        "accuracy": accuracy,
        "rank": rank,
        "total_players": total_players,
        "level": level,
    }


@app.get("/api/profile/achievements")
def api_achievements(x_init_data: str | None = Header(default=None)):
    tg_user = get_user_from_header(x_init_data)
    stats = db.get_user_stats(tg_user["id"]) or {"total_correct": 0, "total_wrong": 0, "total_tests": 0}
    best_percent = db.get_best_attempt_percent(tg_user["id"])
    total = stats["total_correct"] + stats["total_wrong"]
    accuracy = (stats["total_correct"] / total * 100) if total else 0

    defs = [
        {"id": "first_test", "title": "Birinchi qadam", "desc": "Birinchi testni yakunlang",
         "icon": "flag", "unlocked": stats["total_tests"] >= 1},
        {"id": "correct_10", "title": "10 ta to'g'ri", "desc": "Jami 10 ta to'g'ri javob bering",
         "icon": "check", "unlocked": stats["total_correct"] >= 10},
        {"id": "correct_50", "title": "50 ta to'g'ri", "desc": "Jami 50 ta to'g'ri javob bering",
         "icon": "check2", "unlocked": stats["total_correct"] >= 50},
        {"id": "correct_100", "title": "100 ta to'g'ri", "desc": "Jami 100 ta to'g'ri javob bering",
         "icon": "star", "unlocked": stats["total_correct"] >= 100},
        {"id": "tests_10", "title": "Faol o'quvchi", "desc": "10 ta test yakunlang",
         "icon": "fire", "unlocked": stats["total_tests"] >= 10},
        {"id": "tests_30", "title": "Bilimdon", "desc": "30 ta test yakunlang",
         "icon": "book", "unlocked": stats["total_tests"] >= 30},
        {"id": "accuracy_90", "title": "Aniqlik ustasi", "desc": "Umumiy aniqlik 90% dan yuqori",
         "icon": "target", "unlocked": total >= 10 and accuracy >= 90},
        {"id": "perfect", "title": "Sof g'olib", "desc": "Bitta testni 100% natija bilan tugating",
         "icon": "trophy", "unlocked": best_percent >= 100},
    ]
    unlocked_count = sum(1 for a in defs if a["unlocked"])
    return {"achievements": defs, "unlocked": unlocked_count, "total": len(defs)}


@app.get("/api/profile/breakdown")
def api_breakdown(x_init_data: str | None = Header(default=None)):
    tg_user = get_user_from_header(x_init_data)
    rows = db.get_subject_breakdown(tg_user["id"])
    result = []
    for r in rows:
        total = (r["correct"] or 0) + (r["wrong"] or 0)
        pct = round((r["correct"] or 0) / total * 100) if total else 0
        result.append({"subject": r["subject"], "correct": r["correct"] or 0,
                        "wrong": r["wrong"] or 0, "tests": r["tests"], "accuracy": pct})
    return {"breakdown": result}


# ---------- Reyting ----------
@app.get("/api/rating/all")
def api_rating_all(x_init_data: str | None = Header(default=None)):
    tg_user = get_user_from_header(x_init_data)
    top = db.get_top(20)
    rank, total_players = db.get_user_rank(tg_user["id"])
    return {"top": top, "my_rank": rank, "total_players": total_players}


@app.get("/api/rating/season")
def api_rating_season(x_init_data: str | None = Header(default=None)):
    tg_user = get_user_from_header(x_init_data)
    top = db.get_season_top(20)
    rank, total_players = db.get_season_rank(tg_user["id"])
    return {"top": top, "my_rank": rank, "total_players": total_players}


# ---------- Testlar daraxti (sinf -> fan -> mavzu) ----------
@app.get("/api/tests/tree")
def api_tests_tree(x_init_data: str | None = Header(default=None)):
    get_user_from_header(x_init_data)  # faqat avtorizatsiyani tekshiramiz
    tree = []
    for class_num in db.get_classes():
        subjects = []
        for subject in db.get_subjects(class_num):
            topics = []
            for topic in db.get_topics(class_num, subject):
                cnt = db.get_question_count(class_num=class_num, subject=subject, topic=topic)
                topics.append({"name": topic, "count": cnt})
            subjects.append({
                "name": subject,
                "count": db.get_question_count(class_num=class_num, subject=subject),
                "topics": topics,
            })
        tree.append({"class_num": class_num, "subjects": subjects})
    return {"tree": tree, "total_questions": db.get_question_count()}


# ---------- Test jarayoni ----------
def _prepare_questions(raw: list[dict]) -> list[dict]:
    pool = raw.copy()
    random.shuffle(pool)
    chosen = pool[:QUESTIONS_PER_TEST] if len(pool) > QUESTIONS_PER_TEST else pool
    prepared = []
    for q in chosen:
        opts = q["options"].copy()
        random.shuffle(opts)
        prepared.append({"q": q["q"], "options": opts, "correct": q["correct"]})
    return prepared


@app.post("/api/test/start")
def api_test_start(req: TestStartRequest, x_init_data: str | None = Header(default=None)):
    tg_user = get_user_from_header(x_init_data)
    ensure_user(tg_user)

    if req.mode == "mixed":
        raw = db.get_all_questions()
        subject_label, topic_label = "Aralash", "Aralash"
    elif req.mode == "class":
        if req.class_num is None or not req.subject:
            raise HTTPException(400, "class_num va subject kerak")
        raw = db.get_questions_by_subject(req.class_num, req.subject)
        subject_label, topic_label = req.subject, "Barcha mavzular"
    elif req.mode == "topic":
        if req.class_num is None or not req.subject or not req.topic:
            raise HTTPException(400, "class_num, subject, topic kerak")
        raw = db.get_questions_by_topic(req.class_num, req.subject, req.topic)
        subject_label, topic_label = req.subject, req.topic
    else:
        raise HTTPException(400, "Noto'g'ri mode")

    if not raw:
        raise HTTPException(404, "Bu bo'limda hozircha savollar yo'q")

    prepared = _prepare_questions(raw)
    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {
        "user_id": tg_user["id"],
        "mode": req.mode,
        "class_num": req.class_num,
        "subject": subject_label,
        "topic": topic_label,
        "questions": prepared,
        "correct": 0,
        "wrong": 0,
    }
    public_questions = [{"q": q["q"], "options": q["options"]} for q in prepared]
    return {"session_id": session_id, "questions": public_questions}


@app.post("/api/test/answer")
def api_test_answer(req: AnswerRequest, x_init_data: str | None = Header(default=None)):
    tg_user = get_user_from_header(x_init_data)
    session = SESSIONS.get(req.session_id)
    if not session or session["user_id"] != tg_user["id"]:
        raise HTTPException(404, "Sessiya topilmadi")
    if not (0 <= req.question_index < len(session["questions"])):
        raise HTTPException(400, "Noto'g'ri savol raqami")

    q = session["questions"][req.question_index]
    is_correct = req.chosen_index is not None and 0 <= req.chosen_index < len(q["options"]) \
        and q["options"][req.chosen_index] == q["correct"]

    if is_correct:
        session["correct"] += 1
    else:
        session["wrong"] += 1

    return {"correct": is_correct, "correct_answer": q["correct"]}


@app.post("/api/test/finish")
def api_test_finish(req: FinishRequest, x_init_data: str | None = Header(default=None)):
    tg_user = get_user_from_header(x_init_data)
    session = SESSIONS.pop(req.session_id, None)
    if not session or session["user_id"] != tg_user["id"]:
        raise HTTPException(404, "Sessiya topilmadi")

    correct, wrong = session["correct"], session["wrong"]
    total = correct + wrong
    percent = round(correct / total * 100) if total else 0

    db.save_attempt(
        user_id=tg_user["id"], mode=session["mode"], class_num=session["class_num"],
        subject=session["subject"], topic=session["topic"],
        correct=correct, wrong=wrong, total=total,
    )
    return {"correct": correct, "wrong": wrong, "total": total, "percent": percent}


# ---------- Statik fayllar (Mini App frontend) ----------
app.mount("/assets", StaticFiles(directory=str(STATIC_DIR)), name="assets")


@app.get("/")
def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))
