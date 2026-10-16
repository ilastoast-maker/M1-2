const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const state = {
  config: null,
  firebaseAuth: null,
  firebaseUser: null,
  demo: false,
  profile: null,
  records: [],
  summary: null,
  conversation: null,
  pendingGoal: null,
  charts: { steps: null, weight: null },
};

const todaySeoul = () => new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
}).format(new Date());

function showLoading(message = "잠시만 기다려 주세요.") {
  $("#loading-text").textContent = message;
  $("#loading-overlay").classList.remove("hidden");
}

function hideLoading() { $("#loading-overlay").classList.add("hidden"); }

let toastTimer;
function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.add("hidden"), 3200);
}

async function loadConfig() {
  try {
    const response = await fetch("/api/config", { cache: "no-store" });
    if (!response.ok) throw new Error("runtime config unavailable");
    return response.json();
  } catch {
    return {
      apiBaseUrl: "http://localhost:8000",
      authMode: "dev",
      firebase: {},
    };
  }
}

async function authHeaders(extra = {}) {
  const headers = { ...extra };
  if (state.demo) {
    headers["X-Debug-User"] = "demo-user";
  } else if (state.firebaseUser) {
    headers.Authorization = `Bearer ${await state.firebaseUser.getIdToken()}`;
  }
  return headers;
}

async function api(path, options = {}) {
  const isForm = options.body instanceof FormData;
  const headers = await authHeaders(isForm ? options.headers : { "Content-Type": "application/json", ...options.headers });
  const response = await fetch(`${state.config.apiBaseUrl}${path}`, { ...options, headers });
  if (response.status === 204) return null;
  const type = response.headers.get("content-type") || "";
  const payload = type.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = payload?.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).join(" ")
      : detail || "요청을 처리하지 못했습니다.";
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return payload;
}

function setSignedIn(signedIn) {
  $("#auth-view").classList.toggle("hidden", signedIn);
  $("#app-view").classList.toggle("hidden", !signedIn);
}

async function setupAuth() {
  if (state.config.authMode === "dev" || !state.config.firebase?.apiKey) {
    $("#google-sign-in").classList.add("hidden");
    $("#demo-sign-in").classList.remove("hidden");
    return;
  }
  const [{ initializeApp }, authModule] = await Promise.all([
    import("https://www.gstatic.com/firebasejs/11.10.0/firebase-app.js"),
    import("https://www.gstatic.com/firebasejs/11.10.0/firebase-auth.js"),
  ]);
  const app = initializeApp(state.config.firebase);
  state.firebaseAuth = {
    auth: authModule.getAuth(app),
    provider: new authModule.GoogleAuthProvider(),
    signInWithPopup: authModule.signInWithPopup,
    signOut: authModule.signOut,
  };
  authModule.onAuthStateChanged(state.firebaseAuth.auth, async (user) => {
    state.firebaseUser = user;
    setSignedIn(Boolean(user));
    if (user) await hydrate();
  });
}

function navigate(page) {
  $$(".page").forEach((element) => element.classList.toggle("active", element.dataset.page === page));
  $$(".nav-item").forEach((element) => element.classList.toggle("active", element.dataset.nav === page));
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (page === "chat") setTimeout(() => $("#chat-input").focus(), 100);
}

function formatNumber(value, digits = 0) {
  if (value === null || value === undefined) return "—";
  return Number(value).toLocaleString("ko-KR", { maximumFractionDigits: digits });
}

function renderSummary() {
  const summary = state.summary;
  if (!summary) return;
  $("#average-steps").textContent = formatNumber(summary.recent_average_steps || summary.activity.average_steps);
  $("#activity-count").textContent = formatNumber(summary.activity_count);
  $("#latest-weight").textContent = formatNumber(summary.weight.latest_kg, 1);
  $("#trend-text").textContent = summary.trend;
  $("#period-label").textContent = summary.period_start
    ? `${summary.period_start.slice(5).replace("-", ".")}–${summary.period_end.slice(5).replace("-", ".")}`
    : "기록 없음";
  const goal = state.profile?.step_goal;
  $("#step-goal").textContent = goal ? formatNumber(goal) : "—";
  $("#settings-goal").textContent = goal ? `현재 목표 ${formatNumber(goal)}보` : "아직 추천받지 않았어요.";
  const latestActivity = state.records.find((item) => item.record_type === "activity");
  const progress = goal && latestActivity ? Math.min(100, Math.round((latestActivity.value / goal) * 100)) : 0;
  $("#goal-percent").textContent = `${progress}%`;
  $(".goal-ring").style.setProperty("--goal-progress", `${progress * 3.6}deg`);
  $("#goal-caption").textContent = goal
    ? "목표는 최근 흐름에 맞춰 매주 다시 제안해요."
    : "기록이 쌓이면 무리 없는 목표를 추천할게요.";
}

function chartTheme() {
  const styles = getComputedStyle(document.documentElement);
  return {
    ink: styles.getPropertyValue("--ink").trim(),
    muted: styles.getPropertyValue("--muted").trim(),
    coral: styles.getPropertyValue("--coral").trim(),
    mint: styles.getPropertyValue("--mint").trim(),
    line: styles.getPropertyValue("--line").trim(),
  };
}

function buildChart(canvasId, labels, values, label, color, fill = false) {
  if (!window.Chart) return null;
  const theme = chartTheme();
  return new window.Chart($(canvasId), {
    type: fill ? "line" : "bar",
    data: { labels, datasets: [{ label, data: values, borderColor: color, backgroundColor: fill ? `${color}33` : color, borderRadius: 9, tension: 0.35, fill }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: theme.muted, maxTicksLimit: 7 } },
        y: { beginAtZero: !fill, grid: { color: theme.line }, ticks: { color: theme.muted, maxTicksLimit: 5 } },
      },
    },
  });
}

function renderCharts() {
  const theme = chartTheme();
  state.charts.steps?.destroy();
  state.charts.weight?.destroy();
  const activities = state.records.filter((item) => item.record_type === "activity").slice(0, 30).reverse();
  const weights = state.records.filter((item) => item.record_type === "weight").slice(0, 20).reverse();
  state.charts.steps = buildChart("#steps-chart", activities.map((item) => item.date.slice(5)), activities.map((item) => item.value), "걸음 수", theme.coral);
  state.charts.weight = buildChart("#weight-chart", weights.map((item) => item.date.slice(5)), weights.map((item) => item.value), "체중", theme.mint, true);
}

function renderRecords() {
  const root = $("#record-list");
  if (!state.records.length) {
    root.innerHTML = '<p class="empty-state">아직 기록이 없어요. 삼성 헬스 화면 한 장으로 시작해 보세요.</p>';
    return;
  }
  root.innerHTML = state.records.slice(0, 30).map((item) => {
    const [year, month, day] = item.date.split("-");
    const isActivity = item.record_type === "activity";
    const title = isActivity ? `${formatNumber(item.value)}보` : `${formatNumber(item.value, 1)}kg`;
    const detail = isActivity
      ? `${formatNumber(item.active_minutes)}분 · ${formatNumber(item.activity_calories, 1)}kcal · ${formatNumber(item.distance_km, 2)}km`
      : item.memo || "체중 체크인";
    return `<article class="record-item">
      <div class="record-date"><small>${year}</small>${month}.${day}</div>
      <div class="record-copy"><strong>${title}</strong><small>${detail}</small></div>
      <button class="delete-record" data-delete-record="${item.id}" type="button" aria-label="${item.date} 기록 삭제">×</button>
    </article>`;
  }).join("");
}

function fillProfile() {
  if (!state.profile) return;
  $("#profile-age").value = state.profile.age;
  $("#profile-sex").value = state.profile.sex;
  $("#profile-height").value = state.profile.height_cm;
  $("#profile-weight").value = state.profile.current_weight_kg;
  $("#profile-target").value = state.profile.target_weight_kg;
  $("#bmi-guidance").classList.toggle("hidden", !state.profile.bmi_guidance);
  $("#bmi-guidance").textContent = state.profile.bmi_guidance || "";
  if (state.profile.pending_step_goal) showPendingGoal(state.profile.pending_step_goal, "최근 기록을 반영한 대기 중인 제안이에요.");
}

function renderConversation() {
  const messages = state.conversation?.messages || [];
  const chat = $("#chat-messages");
  chat.innerHTML = messages.length
    ? messages.map((message) => `<div class="message ${message.role}">${escapeHtml(message.content)}</div>`).join("")
    : '<div class="message assistant">최근 운동 기록을 바탕으로 궁금한 점을 물어보세요.</div>';
  chat.scrollTop = chat.scrollHeight;

  const history = $("#history-messages");
  let lastDay = "";
  history.innerHTML = messages.map((message) => {
    const day = new Date(message.created_at).toLocaleDateString("ko-KR", { timeZone: "Asia/Seoul" });
    const heading = day !== lastDay ? `<p class="history-day">${day}</p>` : "";
    lastDay = day;
    return `${heading}<div class="history-row"><strong>${message.role === "user" ? "나" : "일어나"}</strong><p>${escapeHtml(message.content)}</p></div>`;
  }).join("");
  $("#conversation-updated").textContent = state.conversation?.updated_at
    ? new Date(state.conversation.updated_at).toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })
    : "아직 대화가 없어요";
}

function escapeHtml(text) {
  const element = document.createElement("div");
  element.textContent = text;
  return element.innerHTML;
}

function updateWeightReminder() {
  const skipped = localStorage.getItem("ileona-weight-skip-until");
  if (skipped && skipped >= todaySeoul()) return;
  const latest = state.records.find((item) => item.record_type === "weight");
  const due = !latest || (Date.now() - new Date(`${latest.date}T00:00:00+09:00`).getTime()) >= 7 * 86400000;
  $("#weight-reminder").classList.toggle("hidden", !due);
}

async function hydrate() {
  showLoading("내 기록을 불러오고 있어요.");
  try {
    try { state.profile = await api("/api/profile"); } catch (error) {
      if (error.status !== 404) throw error;
      state.profile = null;
    }
    const [records, summary, conversations] = await Promise.all([
      api("/api/data?limit=500"),
      api("/api/data/summary"),
      api("/api/conversations"),
    ]);
    state.records = records.items;
    state.summary = summary;
    state.conversation = conversations.items[0] || null;
    fillProfile();
    renderSummary();
    renderRecords();
    renderConversation();
    renderCharts();
    updateWeightReminder();
    if (!state.profile) {
      navigate("settings");
      toast("먼저 기본 정보를 입력해 주세요.");
    }
  } catch (error) {
    toast(error.message);
  } finally {
    hideLoading();
  }
}

function showPendingGoal(steps, reason, safetyNotice = "") {
  state.pendingGoal = steps;
  $("#pending-goal").textContent = formatNumber(steps);
  $("#pending-goal-reason").textContent = [reason, safetyNotice].filter(Boolean).join(" ");
  $("#pending-goal-card").classList.remove("hidden");
}

function setupEvents() {
  $$("[data-nav]").forEach((button) => button.addEventListener("click", () => navigate(button.dataset.nav)));
  $$("[data-open-weight]").forEach((button) => button.addEventListener("click", () => $("#weight-dialog").showModal()));

  $("#demo-sign-in").addEventListener("click", async () => {
    state.demo = true;
    setSignedIn(true);
    await hydrate();
  });

  $("#google-sign-in").addEventListener("click", async () => {
    try { await state.firebaseAuth.signInWithPopup(state.firebaseAuth.auth, state.firebaseAuth.provider); }
    catch { toast("Google 로그인을 완료하지 못했습니다."); }
  });

  $("#sign-out").addEventListener("click", async () => {
    if (state.demo) { state.demo = false; setSignedIn(false); return; }
    await state.firebaseAuth.signOut(state.firebaseAuth.auth);
  });

  $("#theme-toggle").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("ileona-theme", next);
    renderCharts();
  });

  $("#health-image").addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (!file) return;
    const preview = $("#image-preview");
    preview.src = URL.createObjectURL(file);
    preview.classList.remove("hidden");
  });

  $("#extract-image").addEventListener("click", async () => {
    const file = $("#health-image").files[0];
    if (!$("#record-date").value) return toast("기록 날짜를 먼저 선택해 주세요.");
    if (!file) return toast("삼성 헬스 화면을 선택해 주세요.");
    if (!$("#image-consent").checked) return toast("이미지 처리 안내를 확인해 주세요.");
    const form = new FormData();
    form.append("image", file);
    form.append("consent", "true");
    showLoading("화면에서 운동 기록을 읽고 있어요.");
    try {
      const result = await api("/api/data/import/screenshot", { method: "POST", body: form });
      $("#extract-steps").value = result.steps;
      $("#extract-minutes").value = result.active_minutes;
      $("#extract-calories").value = result.activity_calories;
      $("#extract-distance").value = result.distance_km;
      $("#extraction-confidence").textContent = result.confidence === "high" ? "높은 신뢰도" : "확인 필요";
      $("#extraction-warning").textContent = result.warnings.join(" ");
      $("#extraction-warning").classList.toggle("hidden", !result.warnings.length);
      $("#extraction-form").classList.remove("hidden");
    } catch (error) { toast(error.message); } finally { hideLoading(); }
  });

  $("#extraction-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      date: $("#record-date").value,
      value: Number($("#extract-steps").value),
      memo: $("#extract-memo").value,
      record_type: "activity",
      source: "screenshot",
      active_minutes: Number($("#extract-minutes").value),
      activity_calories: Number($("#extract-calories").value),
      distance_km: Number($("#extract-distance").value),
    };
    try {
      await api("/api/data", { method: "POST", body: JSON.stringify(payload) });
    } catch (error) {
      if (error.status !== 409 || !confirm("같은 날짜의 활동 기록이 있어요. 새 값으로 바꿀까요?")) return toast(error.message);
      await api("/api/data?overwrite=true", { method: "POST", body: JSON.stringify(payload) });
    }
    toast("운동 기록을 저장했어요.");
    $("#extraction-form").classList.add("hidden");
    await hydrate();
  });

  $("#record-list").addEventListener("click", async (event) => {
    const button = event.target.closest("[data-delete-record]");
    if (!button || !confirm("이 기록을 삭제할까요?")) return;
    try { await api(`/api/data/${button.dataset.deleteRecord}`, { method: "DELETE" }); await hydrate(); toast("기록을 삭제했어요."); }
    catch (error) { toast(error.message); }
  });

  $("#weight-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      date: $("#weight-date").value,
      value: Number($("#weight-value").value),
      memo: $("#weight-memo").value,
      record_type: "weight",
      source: "manual",
    };
    try {
      await api("/api/data", { method: "POST", body: JSON.stringify(payload) });
      $("#weight-dialog").close();
      toast("체중을 기록했어요.");
      await hydrate();
    } catch (error) { toast(error.message); }
  });

  $("#profile-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      age: Number($("#profile-age").value),
      sex: $("#profile-sex").value,
      height_cm: Number($("#profile-height").value),
      current_weight_kg: Number($("#profile-weight").value),
      target_weight_kg: Number($("#profile-target").value),
      low_bmi_goal_confirmed: $("#low-bmi-confirm").checked,
    };
    const targetBmi = payload.target_weight_kg / ((payload.height_cm / 100) ** 2);
    if (targetBmi < 17 && !payload.low_bmi_goal_confirmed) {
      $("#low-bmi-confirm-row").classList.remove("hidden");
      return toast("낮은 목표 체중에 대한 확인이 필요합니다.");
    }
    try { state.profile = await api("/api/profile", { method: "PUT", body: JSON.stringify(payload) }); fillProfile(); renderSummary(); toast("프로필을 저장했어요."); }
    catch (error) { toast(error.message); }
  });

  $("#recommend-goal").addEventListener("click", async () => {
    showLoading("최근 흐름에 맞는 목표를 생각하고 있어요.");
    try {
      const recommendation = await api("/api/profile/step-goal/recommend", { method: "POST", body: "{}" });
      showPendingGoal(recommendation.recommended_steps, recommendation.reason, recommendation.safety_notice);
    } catch (error) { toast(error.message); } finally { hideLoading(); }
  });

  $("#accept-goal").addEventListener("click", async () => {
    if (!state.pendingGoal) return;
    try {
      state.profile = await api("/api/profile/step-goal/accept", { method: "POST", body: JSON.stringify({ steps: state.pendingGoal }) });
      $("#pending-goal-card").classList.add("hidden");
      state.pendingGoal = null;
      renderSummary();
      fillProfile();
      toast("새 걸음 목표를 적용했어요.");
    } catch (error) { toast(error.message); }
  });

  $("#chat-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = $("#chat-input");
    const message = input.value.trim();
    if (!message) return;
    input.value = "";
    $("#chat-messages").insertAdjacentHTML("beforeend", `<div class="message user">${escapeHtml(message)}</div><div id="chat-wait" class="message assistant loading">기록을 살펴보고 있어요…</div>`);
    try {
      const result = await api("/api/chat", { method: "POST", body: JSON.stringify({ message }) });
      state.conversation = result.conversation;
      renderConversation();
    } catch (error) { $("#chat-wait")?.remove(); toast(error.message); }
  });

  $("#current-conversation").addEventListener("click", () => navigate("chat"));
  $("#clear-chat").addEventListener("click", async () => {
    if (!state.conversation || !confirm("지금까지의 대화를 모두 삭제할까요?")) return;
    try { await api("/api/conversations/primary", { method: "DELETE" }); state.conversation = null; renderConversation(); toast("대화를 초기화했어요."); }
    catch (error) { toast(error.message); }
  });

  $("#download-csv").addEventListener("click", async () => {
    try {
      const headers = await authHeaders();
      const response = await fetch(`${state.config.apiBaseUrl}/api/data/export.csv`, { headers });
      if (!response.ok) throw new Error("CSV를 만들지 못했습니다.");
      const link = document.createElement("a");
      link.href = URL.createObjectURL(await response.blob());
      link.download = "ileona-data.csv";
      link.click();
      URL.revokeObjectURL(link.href);
    } catch (error) { toast(error.message); }
  });

  $("#dismiss-weight-reminder").addEventListener("click", () => {
    const nextWeek = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10);
    localStorage.setItem("ileona-weight-skip-until", nextWeek);
    $("#weight-reminder").classList.add("hidden");
  });

  $("#delete-account").addEventListener("click", async () => {
    const answer = prompt("모든 기록과 대화를 삭제하려면 DELETE를 입력해 주세요.");
    if (answer !== "DELETE") return;
    try {
      await api("/api/account", { method: "DELETE", body: JSON.stringify({ confirmation: "DELETE" }) });
      toast("저장된 데이터를 삭제했습니다.");
      if (state.demo) { state.demo = false; setSignedIn(false); }
      else await state.firebaseAuth.signOut(state.firebaseAuth.auth);
    } catch (error) { toast(error.message); }
  });
}

async function init() {
  const preferred = localStorage.getItem("ileona-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.dataset.theme = preferred;
  $("#record-date").value = todaySeoul();
  $("#weight-date").value = todaySeoul();
  setupEvents();
  state.config = await loadConfig();
  await setupAuth();
}

init().catch((error) => toast(error.message));
