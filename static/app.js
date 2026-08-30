// ============ Telegram WebApp sozlash ============
const tg = window.Telegram ? window.Telegram.WebApp : null;
if (tg) {
  tg.ready();
  tg.expand();
  try { tg.setHeaderColor('#F3F1FA'); } catch (e) {}
}
const INIT_DATA = tg ? tg.initData : "";

// ============ API yordamchisi ============
async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Init-Data": INIT_DATA,
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = "Xatolik yuz berdi";
    try { detail = (await res.json()).detail || detail; } catch (e) {}
    throw new Error(detail);
  }
  return res.json();
}

function showToast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => t.classList.add("hidden"), 2600);
}

// ============ Tab navigatsiya ============
const TABS = ["home", "tests", "season", "rating", "profile"];
function goToTab(tab) {
  TABS.forEach((t) => {
    document.getElementById(`tab-${t}`).classList.toggle("active", t === tab);
  });
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  if (tab === "home") loadHome();
  if (tab === "tests") loadTestsRoot();
  if (tab === "season") loadSeason();
  if (tab === "rating") loadRating();
  if (tab === "profile") loadProfile();
}

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => goToTab(btn.dataset.tab));
});
document.querySelectorAll("[data-goto]").forEach((el) => {
  el.addEventListener("click", () => goToTab(el.dataset.goto));
});

// ============ BOSH ============
async function loadHome() {
  try {
    const me = await api("/api/me");
    document.getElementById("homeGreeting").textContent = `Salom, ${me.first_name}! 👋`;
    document.getElementById("homeAccuracy").textContent = me.total_tests ? `${me.accuracy}%` : "—";
    document.getElementById("homeTests").textContent = me.total_tests;
    document.getElementById("homeRank").textContent = me.rank ? `#${me.rank}` : "—";
    document.getElementById("levelValue").textContent = me.level;
  } catch (e) {
    showToast(e.message);
  }
}
document.getElementById("homeStartBtn").addEventListener("click", () => goToTab("tests"));

// ============ TESTLAR (daraxt) ============
let TREE = null;
let currentClass = null;
let currentSubject = null;

async function loadTestsRoot() {
  showTestsView("tree");
  if (TREE) { renderClassGrid(); return; }
  try {
    const data = await api("/api/tests/tree");
    TREE = data.tree;
    renderClassGrid();
  } catch (e) {
    showToast(e.message);
  }
}

function showTestsView(view) {
  document.getElementById("testsTreeWrap").classList.toggle("hidden", view !== "tree");
  document.getElementById("subjectsWrap").classList.toggle("hidden", view !== "subjects");
  document.getElementById("topicsWrap").classList.toggle("hidden", view !== "topics");
}

function renderClassGrid() {
  const grid = document.getElementById("classGrid");
  if (!TREE || TREE.length === 0) {
    grid.innerHTML = `<div class="loading-text">Hozircha savollar yo'q. O'qituvchi tez orada qo'shadi 🙌</div>`;
    return;
  }
  grid.innerHTML = "";
  TREE.forEach((cls) => {
    const btn = document.createElement("button");
    btn.className = "class-card";
    btn.innerHTML = `<div class="class-num">${cls.class_num}</div><div class="class-label">sinf</div>`;
    btn.addEventListener("click", () => openClass(cls));
    grid.appendChild(btn);
  });
}

function openClass(cls) {
  currentClass = cls;
  document.getElementById("subjectsTitle").textContent = `${cls.class_num}-sinf — fan tanlang`;
  const list = document.getElementById("subjectsList");
  list.innerHTML = "";
  cls.subjects.forEach((subj) => {
    const row = document.createElement("button");
    row.className = "menu-row";
    row.innerHTML = `
      <span class="menu-icon" style="background:linear-gradient(135deg,#8B7CF6,#6C5CE7)">${subj.name.includes("Jahon") ? "🌍" : "🏛"}</span>
      <span class="menu-text">
        <span class="menu-title">${subj.name}</span>
        <span class="menu-sub">${subj.topics.length} ta mavzu</span>
      </span>
      <span class="menu-count">${subj.count} savol</span>`;
    row.addEventListener("click", () => openSubject(subj));
    list.appendChild(row);
  });
  showTestsView("subjects");
}

function openSubject(subj) {
  currentSubject = subj;
  document.getElementById("topicsTitle").textContent = `${currentClass.class_num}-sinf — ${subj.name}`;
  const list = document.getElementById("topicsList");
  list.innerHTML = "";

  const allRow = document.createElement("button");
  allRow.className = "menu-row";
  allRow.innerHTML = `
    <span class="menu-icon" style="background:linear-gradient(135deg,#FFC15E,#FF9F3E)">📚</span>
    <span class="menu-text">
      <span class="menu-title">Barcha mavzular</span>
      <span class="menu-sub">Shu fandan aralash</span>
    </span>
    <span class="menu-count">${subj.count} savol</span>`;
  allRow.addEventListener("click", () =>
    startTest({ mode: "class", class_num: currentClass.class_num, subject: subj.name })
  );
  list.appendChild(allRow);

  subj.topics.forEach((topic) => {
    const row = document.createElement("button");
    row.className = "menu-row";
    row.innerHTML = `
      <span class="menu-icon" style="background:linear-gradient(135deg,#6ED0FF,#3AA9F0)">📖</span>
      <span class="menu-text">
        <span class="menu-title">${topic.name}</span>
      </span>
      <span class="menu-count">${topic.count} savol</span>`;
    row.addEventListener("click", () =>
      startTest({ mode: "topic", class_num: currentClass.class_num, subject: subj.name, topic: topic.name })
    );
    list.appendChild(row);
  });

  showTestsView("topics");
}

document.getElementById("backToClasses").addEventListener("click", () => showTestsView("tree"));
document.getElementById("backToSubjects").addEventListener("click", () => showTestsView("subjects"));
document.getElementById("mixedTestBtn").addEventListener("click", () => startTest({ mode: "mixed" }));

// ============ TEST JARAYONI ============
const TIMER_SECONDS = 15;
let quizState = null; // {session_id, questions, index, timerTimeout, answered}

async function startTest(payload) {
  try {
    const data = await api("/api/test/start", { method: "POST", body: JSON.stringify(payload) });
    quizState = {
      session_id: data.session_id,
      questions: data.questions,
      index: 0,
      answered: false,
    };
    document.getElementById("quizOverlay").classList.remove("hidden");
    renderQuestion();
  } catch (e) {
    showToast(e.message);
  }
}

function renderQuestion() {
  const q = quizState.questions[quizState.index];
  const total = quizState.questions.length;
  document.getElementById("quizQnum").textContent = `Savol ${quizState.index + 1}/${total}`;
  document.getElementById("quizQuestion").textContent = q.q;
  document.getElementById("quizProgressFill").style.width = `${(quizState.index / total) * 100}%`;

  const optionsWrap = document.getElementById("quizOptions");
  optionsWrap.innerHTML = "";
  q.options.forEach((opt, i) => {
    const btn = document.createElement("button");
    btn.className = "quiz-option";
    btn.textContent = opt;
    btn.addEventListener("click", () => submitAnswer(i));
    optionsWrap.appendChild(btn);
  });

  quizState.answered = false;
  startTimer();
}

function startTimer() {
  const circle = document.getElementById("timerCircle");
  const number = document.getElementById("timerNumber");
  const CIRCUMFERENCE = 119.4;

  circle.classList.remove("danger");
  circle.style.transition = "none";
  circle.style.strokeDashoffset = "0";
  // reflow
  void circle.offsetWidth;
  circle.style.transition = `stroke-dashoffset ${TIMER_SECONDS}s linear, stroke .3s ease`;
  circle.style.strokeDashoffset = String(CIRCUMFERENCE);

  let remaining = TIMER_SECONDS;
  number.textContent = remaining;
  clearInterval(quizState.tickInterval);
  quizState.tickInterval = setInterval(() => {
    remaining -= 1;
    number.textContent = Math.max(remaining, 0);
    if (remaining <= 5) circle.classList.add("danger");
    if (remaining <= 0) clearInterval(quizState.tickInterval);
  }, 1000);

  clearTimeout(quizState.timerTimeout);
  quizState.timerTimeout = setTimeout(() => {
    if (!quizState.answered) submitAnswer(null);
  }, TIMER_SECONDS * 1000);
}

async function submitAnswer(chosenIndex) {
  if (quizState.answered) return;
  quizState.answered = true;
  clearTimeout(quizState.timerTimeout);
  clearInterval(quizState.tickInterval);

  const options = document.querySelectorAll(".quiz-option");
  options.forEach((o) => o.classList.add("disabled"));

  try {
    const res = await api("/api/test/answer", {
      method: "POST",
      body: JSON.stringify({
        session_id: quizState.session_id,
        question_index: quizState.index,
        chosen_index: chosenIndex,
      }),
    });

    options.forEach((o) => {
      if (o.textContent === res.correct_answer) o.classList.add("correct");
      else if (chosenIndex !== null && o.textContent === quizState.questions[quizState.index].options[chosenIndex] && !res.correct)
        o.classList.add("wrong");
    });

    if (tg && tg.HapticFeedback) {
      tg.HapticFeedback.notificationOccurred(res.correct ? "success" : "error");
    }

    setTimeout(nextQuestion, 1100);
  } catch (e) {
    showToast(e.message);
  }
}

function nextQuestion() {
  quizState.index += 1;
  if (quizState.index >= quizState.questions.length) {
    finishTest();
  } else {
    renderQuestion();
  }
}

async function finishTest() {
  document.getElementById("quizProgressFill").style.width = "100%";
  try {
    const res = await api("/api/test/finish", {
      method: "POST",
      body: JSON.stringify({ session_id: quizState.session_id }),
    });
    document.getElementById("quizOverlay").classList.add("hidden");
    showResult(res);
  } catch (e) {
    showToast(e.message);
    document.getElementById("quizOverlay").classList.add("hidden");
  }
  quizState = null;
}

function showResult(res) {
  document.getElementById("resultOverlay").classList.remove("hidden");
  document.getElementById("resultCorrect").textContent = res.correct;
  document.getElementById("resultWrong").textContent = res.wrong;
  document.getElementById("resultPercent").textContent = `${res.percent}%`;

  const titles = [
    [90, "A'lo natija! 🎉"], [70, "Zo'r ish! 👏"], [50, "Yaxshi urinish! 💪"], [0, "Davom eting! 📚"],
  ];
  document.getElementById("resultTitle").textContent = titles.find(([min]) => res.percent >= min)[1];

  const ring = document.getElementById("resultRing");
  const CIRC = 327;
  ring.style.transition = "none";
  ring.style.strokeDashoffset = String(CIRC);
  void ring.offsetWidth;
  ring.style.transition = "stroke-dashoffset 1s ease";
  ring.style.strokeDashoffset = String(CIRC - (CIRC * res.percent) / 100);
}

document.getElementById("quizCloseBtn").addEventListener("click", () => {
  if (quizState) {
    clearTimeout(quizState.timerTimeout);
    clearInterval(quizState.tickInterval);
    quizState = null;
  }
  document.getElementById("quizOverlay").classList.add("hidden");
});

document.getElementById("resultRestartBtn").addEventListener("click", () => {
  document.getElementById("resultOverlay").classList.add("hidden");
  goToTab("tests");
});
document.getElementById("resultHomeBtn").addEventListener("click", () => {
  document.getElementById("resultOverlay").classList.add("hidden");
  goToTab("home");
});

// ============ MAVSUM / REYTING ============
const PODIUM_COLORS = [
  "linear-gradient(135deg,#FFC15E,#FF9F3E)", // 1-o'rin — oltin
  "linear-gradient(135deg,#C7D0DB,#98A3B3)", // 2-o'rin — kumush
  "linear-gradient(135deg,#E3A874,#C97B3D)", // 3-o'rin — bronza
];

function renderPodium(container, top, ballKey, testsKey) {
  container.innerHTML = "";
  const top3 = top.slice(0, 3);
  if (!top3.length) return;

  // Ko'rgazmali tartib: 2-o'rin chapda, 1-o'rin markazda (baland), 3-o'rin o'ngda
  [1, 0, 2].forEach((idx) => {
    const u = top3[idx];
    if (!u) return;
    const rank = idx + 1;
    const initial = (u.full_name || "?").trim().charAt(0).toUpperCase();
    const card = document.createElement("div");
    card.className = `podium-card rank-${rank}`;
    card.innerHTML = `
      ${rank === 1 ? '<div class="podium-crown">👑</div>' : ""}
      <div class="podium-avatar" style="background:${PODIUM_COLORS[rank - 1]}">${initial}</div>
      <div class="podium-name">${u.full_name || "Foydalanuvchi"}</div>
      <div class="podium-ball">${u[ballKey] || 0} ball</div>
      <div class="podium-sub">${u[testsKey] || 0} test</div>
      <div class="podium-medal-badge" style="background:${PODIUM_COLORS[rank - 1]}">${rank}</div>`;
    container.appendChild(card);
  });
}

function renderRatingList(container, top, myId, ballKey) {
  container.innerHTML = "";
  const rest = top.slice(3);
  if (!top.length) {
    container.innerHTML = `<div class="loading-text">Hozircha hech kim test ishlamagan. Birinchi bo'ling! 🚀</div>`;
    return;
  }
  if (!rest.length) return;

  rest.forEach((u, i) => {
    const rank = i + 4;
    const row = document.createElement("div");
    row.className = "rating-row" + (u.user_id === myId ? " me" : "");
    row.innerHTML = `
      <span class="rating-rank">${rank}</span>
      <span class="rating-name">${u.full_name || "Foydalanuvchi"}</span>
      <span class="rating-score">${u[ballKey] || 0} ball</span>`;
    container.appendChild(row);
  });
}

async function loadRating() {
  const listEl = document.getElementById("ratingList");
  const podiumEl = document.getElementById("ratingPodium");
  const rankEl = document.getElementById("ratingMyRank");
  listEl.innerHTML = `<div class="loading-text">Yuklanmoqda...</div>`;
  podiumEl.innerHTML = "";
  try {
    const me = await api("/api/me");
    const data = await api("/api/rating/all");
    rankEl.textContent = data.my_rank
      ? `Sizning o'rningiz: #${data.my_rank} / ${data.total_players}`
      : "Reytingga kirish uchun test ishlang!";
    renderPodium(podiumEl, data.top, "total_correct", "total_tests");
    renderRatingList(listEl, data.top, me.id, "total_correct");
  } catch (e) {
    showToast(e.message);
  }
}

async function loadSeason() {
  const listEl = document.getElementById("seasonList");
  const podiumEl = document.getElementById("seasonPodium");
  const rankEl = document.getElementById("seasonMyRank");
  listEl.innerHTML = `<div class="loading-text">Yuklanmoqda...</div>`;
  podiumEl.innerHTML = "";
  try {
    const me = await api("/api/me");
    const data = await api("/api/rating/season");
    rankEl.textContent = data.my_rank
      ? `Bu oyda sizning o'rningiz: #${data.my_rank} / ${data.total_players}`
      : "Bu oy hali test ishlamadingiz!";
    renderPodium(podiumEl, data.top, "season_correct", "season_tests");
    renderRatingList(listEl, data.top, me.id, "season_correct");
  } catch (e) {
    showToast(e.message);
  }
}

// ============ PROFIL ============
const ACH_ICONS = {
  flag: "🚩", check: "✅", check2: "✔️", star: "⭐",
  fire: "🔥", book: "📘", target: "🎯", trophy: "🏆",
};

async function loadProfile() {
  try {
    const me = await api("/api/me");
    document.getElementById("profileName").textContent = me.first_name;
    document.getElementById("profileTests").textContent = me.total_tests;
    document.getElementById("profileAccuracy").textContent = me.total_tests ? `${me.accuracy}%` : "—";
    document.getElementById("profileLevelBadge").textContent = me.level;

    const avatarEl = document.getElementById("profileAvatar");
    if (me.photo_url) {
      avatarEl.innerHTML = `<img src="${me.photo_url}" alt="">`;
    } else {
      avatarEl.textContent = (me.first_name || "?").charAt(0).toUpperCase();
    }

    const achData = await api("/api/profile/achievements");
    document.getElementById("achTitle").textContent = `Yutuqlar (${achData.unlocked}/${achData.total})`;
    const achGrid = document.getElementById("achGrid");
    achGrid.innerHTML = "";
    achData.achievements.forEach((a) => {
      const item = document.createElement("div");
      item.className = "ach-item" + (a.unlocked ? " unlocked" : "");
      item.innerHTML = `<div class="ach-icon">${ACH_ICONS[a.icon] || "🏅"}</div><div class="ach-name">${a.title}</div>`;
      achGrid.appendChild(item);
    });

    document.getElementById("adminAddBtn").classList.toggle("hidden", !me.is_admin);
  } catch (e) {
    showToast(e.message);
  }
}

document.getElementById("analysisBtn").addEventListener("click", async () => {
  const wrap = document.getElementById("breakdownWrap");
  if (!wrap.classList.contains("hidden")) {
    wrap.classList.add("hidden");
    return;
  }
  wrap.classList.remove("hidden");
  wrap.innerHTML = `<div class="loading-text">Yuklanmoqda...</div>`;
  try {
    const data = await api("/api/profile/breakdown");
    if (!data.breakdown.length) {
      wrap.innerHTML = `<div class="loading-text">Hali test ishlamagansiz.</div>`;
      return;
    }
    wrap.innerHTML = "";
    data.breakdown.forEach((b) => {
      const row = document.createElement("div");
      row.className = "breakdown-row";
      row.innerHTML = `
        <div class="breakdown-top"><span>${b.subject}</span><span>${b.accuracy}%</span></div>
        <div class="breakdown-bar"><div class="breakdown-bar-fill" style="width:${b.accuracy}%"></div></div>`;
      wrap.appendChild(row);
    });
  } catch (e) {
    showToast(e.message);
  }
});

// ============ ADMIN: SAVOL QO'SHISH ============
let ADMIN_META = null;
let adminSelectedClass = null;
let adminSelectedSubject = null;

function renderAdminOptions() {
  const wrap = document.getElementById("adminOptionsWrap");
  wrap.innerHTML = "";
  for (let i = 0; i < 4; i++) {
    const row = document.createElement("div");
    row.className = "quiz-option";
    row.style.display = "flex";
    row.style.alignItems = "center";
    row.style.gap = "10px";
    row.style.cursor = "default";
    row.innerHTML = `
      <input type="radio" name="adminCorrect" value="${i}" ${i === 0 ? "checked" : ""}
        style="width:18px; height:18px; flex-shrink:0; accent-color:var(--primary);">
      <input type="text" class="admin-option-input" data-idx="${i}" placeholder="${i + 1}-variant"
        style="flex:1; border:none; outline:none; font-size:14px; font-family:var(--font-body); background:transparent;">
    `;
    wrap.appendChild(row);
  }
}

function renderAdminClasses() {
  const grid = document.getElementById("adminClassGrid");
  grid.innerHTML = "";
  (ADMIN_META?.classes || []).forEach((c) => {
    const btn = document.createElement("button");
    btn.className = "class-card";
    btn.innerHTML = `<div class="class-num">${c}</div><div class="class-label">sinf</div>`;
    btn.addEventListener("click", () => {
      adminSelectedClass = c;
      document.querySelectorAll("#adminClassGrid .class-card").forEach((b) => (b.style.outline = ""));
      btn.style.outline = "2px solid var(--primary)";
    });
    grid.appendChild(btn);
  });
}

function renderAdminSubjects() {
  const list = document.getElementById("adminSubjectList");
  list.innerHTML = "";
  (ADMIN_META?.subjects || []).forEach((s) => {
    const row = document.createElement("button");
    row.className = "menu-row";
    row.innerHTML = `
      <span class="menu-icon" style="background:linear-gradient(135deg,#8B7CF6,#6C5CE7)">${s.includes("Jahon") ? "🌍" : "🏛"}</span>
      <span class="menu-text"><span class="menu-title">${s}</span></span>`;
    row.addEventListener("click", () => {
      adminSelectedSubject = s;
      document.querySelectorAll("#adminSubjectList .menu-row").forEach((r) => (r.style.outline = ""));
      row.style.outline = "2px solid var(--primary)";
    });
    list.appendChild(row);
  });
}

async function openAdminOverlay() {
  document.getElementById("adminOverlay").classList.remove("hidden");
  document.getElementById("adminTopicInput").value = "";
  document.getElementById("adminQuestionInput").value = "";
  renderAdminOptions();

  if (!ADMIN_META) {
    try {
      ADMIN_META = await api("/api/admin/meta");
    } catch (e) {
      showToast(e.message);
      document.getElementById("adminOverlay").classList.add("hidden");
      return;
    }
  }
  renderAdminClasses();
  renderAdminSubjects();
}

document.getElementById("adminAddBtn")?.addEventListener("click", openAdminOverlay);
document.getElementById("adminCloseBtn")?.addEventListener("click", () => {
  document.getElementById("adminOverlay").classList.add("hidden");
});

document.getElementById("adminSubmitBtn")?.addEventListener("click", async () => {
  const topic = document.getElementById("adminTopicInput").value.trim();
  const question = document.getElementById("adminQuestionInput").value.trim();
  const optionInputs = document.querySelectorAll(".admin-option-input");
  const options = Array.from(optionInputs).map((el) => el.value.trim());
  const correctRadio = document.querySelector('input[name="adminCorrect"]:checked');

  if (!adminSelectedClass) { showToast("Avval sinfni tanlang"); return; }
  if (!adminSelectedSubject) { showToast("Avval fanni tanlang"); return; }
  if (!topic) { showToast("Mavzu nomini yozing"); return; }
  if (!question) { showToast("Savol matnini yozing"); return; }
  if (options.some((o) => !o)) { showToast("Barcha 4 ta variantni to'ldiring"); return; }

  try {
    await api("/api/admin/question", {
      method: "POST",
      body: JSON.stringify({
        class_num: adminSelectedClass,
        subject: adminSelectedSubject,
        topic: topic,
        question: question,
        options: options,
        correct_index: Number(correctRadio.value),
      }),
    });
    showToast("✅ Savol saqlandi! Yana qo'sha olasiz.");
    document.getElementById("adminQuestionInput").value = "";
    renderAdminOptions();
    TREE = null; // testlar daraxti keshini tozalab, yangi savol darhol ko'rinishi uchun
    if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
  } catch (e) {
    showToast(e.message);
  }
});

// ============ Boshlanish ============
if (!INIT_DATA) {
  showToast("Bu ilova faqat Telegram ichida ishlaydi ⚠️");
}
goToTab("home");
