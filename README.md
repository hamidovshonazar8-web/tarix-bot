# 📚 Tarix Test — Telegram Mini App

O'quvchilar uchun to'liq **Telegram Mini App** (Bosh / Testlar / Mavsum / Reyting / Profil bo'limlari
bilan) + oddiy bot rejimi. Savollarni siz (o'qituvchi) botning o'zida kiritasiz. Har savolga
**15 soniya** vaqt beriladi (Mini App'da aylanma taymer bilan ko'rinadi).

## Loyihaning tuzilishi

| Fayl / papka | Vazifasi |
|---|---|
| `main.py` | **Shu faylni ishga tushirasiz.** Bot va Mini App serverini birga ishga tushiradi |
| `bot_router.py` | Telegram bot logikasi (menyular, admin savol qo'shish, oddiy test rejimi, taymer) |
| `webapp.py` | Mini App backend (FastAPI) — barcha `/api/...` so'rovlarni boshqaradi |
| `auth.py` | Telegram Mini App `initData`sini xavfsiz tekshirish |
| `database.py` | SQLite (foydalanuvchilar, natijalar, savollar, reyting so'rovlari) |
| `config.py` | Token, admin ro'yxati, Mini App manzili |
| `static/` | Mini App frontend (`index.html`, `style.css`, `app.js`) |
| `Procfile` | Railway/Render kabi xizmatlar uchun ishga tushirish buyrug'i |

## 1-qadam: Botni yaratish

1. Telegramda **@BotFather** ga `/newbot` yozing, botga nom bering, tokenni saqlab qo'ying.
2. **@userinfobot** ga `/start` yozib, o'zingizning Telegram ID'ingizni oling (masalan `582910345`).
3. `config.py` faylini oching:
   - `BOT_TOKEN` ni tokeningizga almashtiring (yoki `BOT_TOKEN` muhit o'zgaruvchisi orqali bering)
   - `ADMIN_IDS = [111111111]` dagi raqamni **o'zingiznikiga** almashtiring

## 2-qadam: Joylashtirish (eng oson yo'l — Railway.app)

Mini App internetda **HTTPS** manzilda turishi shart — Telegram uni faqat shu holda ochadi.
Eng sodda va bepul yo'l — **Railway.app**:

1. Bu loyihani GitHub'ga yuklang (yangi repository yarating, fayllarni push qiling).
2. [railway.app](https://railway.app) ga GitHub hisobingiz bilan kiring.
3. **New Project → Deploy from GitHub repo** → shu repositoryni tanlang.
4. Railway avtomatik `requirements.txt`ni o'qib, muhitni tayyorlaydi.
5. **Variables** bo'limida quyidagilarni qo'shing:
   - `BOT_TOKEN` = sizning bot tokeningiz
   - (config.py'da ADMIN_IDS ni to'g'ridan-to'g'ri kod ichida ham qoldirsa bo'ladi)
6. **Settings → Networking → Generate Domain** tugmasini bosing — Railway sizga
   `https://sizning-loyiha.up.railway.app` kabi bepul HTTPS manzil beradi.
7. Shu manzilni nusxalab, **Variables**ga yana bitta o'zgaruvchi qo'shing:
   - `MINIAPP_URL` = `https://sizning-loyiha.up.railway.app`
8. Loyiha qayta deploy bo'ladi (Railway avtomatik qiladi) — tayyor!

> ⚠️ **Eslatma:** Railway bepul rejasida fayl tizimi har deploy'da tozalanishi mumkin, ya'ni
> `tarix_bot.db` fayli (savollar, natijalar) vaqti-vaqti bilan o'chib ketishi ehtimoli bor.
> Uzoq muddatli foydalanish uchun Railway'da **Volume** (doimiy disk) qo'shishni yoki keyinroq
> Postgres bazasiga o'tishni tavsiya qilaman — kerak bo'lsa shuni ham sozlab beraman.

### Muqobil: Render.com
Xuddi shunday — GitHub repo ulanadi, "Web Service" yaratiladi, start buyrug'i `python main.py`,
`BOT_TOKEN` va keyin `MINIAPP_URL` muhit o'zgaruvchilari qo'shiladi.

## 3-qadam: BotFather'da Mini App tugmasini sozlash (ixtiyoriy, lekin tavsiya etiladi)

Bot allaqachon "🎮 Mini ilovani ochish" tugmasini pastki menyuda ko'rsatadi (agar `MINIAPP_URL`
to'g'ri berilgan bo'lsa). Qo'shimcha ravishda, botning **Menu Button**ini ham Mini App qilib
qo'yishingiz mumkin:

1. @BotFather → `/mybots` → botingizni tanlang → **Bot Settings → Menu Button**
2. **Edit Menu Button URL** → Railway bergan HTTPS manzilni kiriting
3. Nom bering, masalan: "Testni boshlash"

## 4-qadam: Ishga tushirish

```bash
pip install -r requirements.txt
python main.py
```

Bitta buyruq bilan **ham bot, ham Mini App serveri** birga ishga tushadi.

## Savol qo'shish (o'qituvchi uchun)

Mini App'dagi savollar xuddi botdagi bilan bir xil bazadan olinadi — botga `/savol_qoshish`
deb yozib kiritasiz (batafsili quyida):

1. `/savol_qoshish` — sinfni tanlaysiz
2. Fanni tanlaysiz: 🏛 O'zbekiston tarixi yoki 🌍 Jahon tarixi
3. Mavzu nomini yozasiz
4. Savol matnini yuborasiz
5. 4 ta variantni **har birini alohida qatorda** yuborasiz
6. Tugmalardan to'g'ri javobni tanlaysiz — saqlanadi ✅ va darhol Mini App'da ham ko'rinadi
7. "Yana shu mavzuga qo'shasizmi?" — Ha desangiz ketma-ket kiritishda davom etasiz

### Admin buyruqlari

| Buyruq | Vazifasi |
|---|---|
| `/savol_qoshish` | Yangi savol kiritish |
| `/savollar_soni` | Bazadagi savollar sonini ko'rsatadi |
| `/oxirgisini_ochir` | Oxirgi qo'shilgan savolni o'chiradi |
| `/bekor` | Joriy amalni bekor qiladi |

## Mini App bo'limlari

- **🏠 Bosh** — salomlashuv, tezkor statistikangiz, "Test boshlash" tugmasi
- **📝 Testlar** — sinf → fan → mavzu bo'yicha yoki 🔀 aralash test
- **🌱 Mavsum** — joriy oy bo'yicha reyting (har oy boshida yangidan boshlanadi)
- **🏆 Reyting** — barcha vaqt bo'yicha TOP-20 va sizning o'rningiz
- **👤 Profil** — daraja (level), yutuqlar (8 xil nishon), fan bo'yicha tahlil

Test jarayonida har savolga **15 soniyalik aylanma taymer** ko'rinadi; vaqt tugasa avtomatik
xato hisoblanib, keyingi savolga o'tiladi. Har javobdan keyin to'g'ri/xato rangda ko'rsatiladi.

## Xavfsizlik haqida

Mini App har bir so'rovda Telegramning `initData`sini serverda **HMAC-SHA256 orqali tasdiqlaydi**
(rasmiy Telegram algoritmi) — shuning uchun hech kim o'zini boshqa foydalanuvchi sifatida
ko'rsata olmaydi va to'g'ri javoblar mijoz tomonida ko'rinmaydi (faqat server biladi).
