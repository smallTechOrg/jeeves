"use strict";

const messagesEl = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");
const factsList = document.getElementById("facts-list");
const filterQ = document.getElementById("filter-q");
const filterCat = document.getElementById("filter-cat");
const summaryEl = document.getElementById("summary");

// Stable per-browser conversation session so Jeeves can carry context across messages.
function getSessionId() {
  let s = localStorage.getItem("jeeves_session");
  if (!s) {
    s = "sess-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem("jeeves_session", s);
  }
  return s;
}
const SESSION_ID = getSessionId();

function addBubble(text, kind) {
  const b = document.createElement("div");
  b.className = "bubble " + (kind || "sys");
  b.textContent = text;
  messagesEl.appendChild(b);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function addAnswerBubble(answer, citations, intent) {
  const b = document.createElement("div");
  b.className = "bubble answer";
  const intentBadge = intent
    ? `<span class="intent intent-${intent}">${intent}</span>`
    : "";
  const head = document.createElement("div");
  head.className = "answer-head";
  head.innerHTML = intentBadge;
  b.appendChild(head);
  const p = document.createElement("div");
  p.className = "answer-text";
  p.textContent = answer;
  b.appendChild(p);
  if (citations && citations.length) {
    const c = document.createElement("div");
    c.className = "citations";
    c.textContent = "↳ from " + citations.length + " fact" + (citations.length === 1 ? "" : "s") +
      ": " + citations.map(x => x.category).join(", ");
    b.appendChild(c);
  }
  messagesEl.appendChild(b);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function addCapturedBubble(facts, intent) {
  const b = document.createElement("div");
  b.className = "bubble answer";
  const head = document.createElement("div");
  head.className = "answer-head";
  head.innerHTML = `<span class="intent intent-fact">${intent || "fact"}</span> <span class="captured-n">Captured ${facts.length} fact${facts.length === 1 ? "" : "s"}</span>`;
  b.appendChild(head);
  const p = document.createElement("div");
  p.className = "answer-text";
  p.textContent = facts.map(f => (f.fact_text || f.category) + (f.fact_date ? ` (${f.fact_date})` : "")).join(" · ");
  b.appendChild(p);
  messagesEl.appendChild(b);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderFacts(facts) {
  factsList.innerHTML = "";
  if (!facts.length) {
    const e = document.createElement("div");
    e.className = "empty";
    e.textContent = "No facts captured yet. Send a message above.";
    factsList.appendChild(e);
    return;
  }
  for (const f of facts) {
    const card = document.createElement("div");
    const status = f.status || "active";
    card.className = "fact status-" + status;
    const conf = Math.round((f.confidence || 0) * 100);
    const confCls = conf >= 60 ? "hi" : "lo";
    const ent = f.entity ? `<span class="ent">· ${escapeHtml(f.entity)}</span>` : "";

    // Derived attributes (the relational/normalized part)
    const attrs = [];
    if (f.quantity != null && f.unit) attrs.push(`${f.quantity} ${escapeHtml(f.unit)}`);
    else if (f.quantity != null) attrs.push(`${f.quantity}`);
    if (f.period) attrs.push(`<span class="period">${escapeHtml(f.period)}</span>`);
    const when = [f.fact_date, f.fact_time].filter(Boolean).join(" ");
    if (when) attrs.push(`<span class="fdate">${escapeHtml(when)}</span>`);
    const attrHtml = attrs.length
      ? `<div class="attrs">` + attrs.map(a => `<span class="attr">${a}</span>`).join("") + `</div>`
      : "";

    const statusBadge = `<span class="badge badge-${status}">${status}</span>`;
    const verifyBtn = (status === "verified")
      ? `<span class="verified-tag">✓ verified</span>`
      : `<button class="fact-btn verify" data-id="${f.id}">Verify</button>`;

    card.innerHTML =
      `<label class="fact-sel"><input type="checkbox" class="fact-check" data-id="${f.id}"></label>` +
      `<div class="meta">` +
        `<span class="cat">${escapeHtml(f.category)}</span>` +
        ent +
        statusBadge +
        `<span class="conf ${confCls}">${conf}% sure</span>` +
      `</div>` +
      `<div class="txt">${escapeHtml(f.fact_text)}</div>` +
      attrHtml +
      `<div class="fact-actions">` +
        verifyBtn +
        `<button class="fact-btn edit" data-id="${f.id}">Edit</button>` +
        `<button class="fact-btn delete" data-id="${f.id}">Delete</button>` +
      `</div>`;
    factsList.appendChild(card);
  }

  // wire verify + edit buttons
  factsList.querySelectorAll(".fact-btn.verify").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-id");
      await fetch(`/api/facts/${id}/verify`, { method: "POST" });
      refreshFacts();
    });
  });
  factsList.querySelectorAll(".fact-btn.edit").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-id");
      const card = btn.closest(".fact");
      const txtEl = card.querySelector(".txt");
      const current = txtEl.textContent;
      const inputEl = document.createElement("input");
      inputEl.type = "text";
      inputEl.value = current;
      inputEl.className = "edit-input";
      txtEl.replaceWith(inputEl);
      inputEl.focus();
      const save = async () => {
        const nv = inputEl.value.trim();
        if (nv && nv !== current) {
          await fetch(`/api/facts/${id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ fact_text: nv }),
          });
        }
        refreshFacts();
      };
      inputEl.addEventListener("blur", save);
      inputEl.addEventListener("keydown", (e) => { if (e.key === "Enter") inputEl.blur(); });
    });
  });

  // per-card delete
  factsList.querySelectorAll(".fact-btn.delete").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-id");
      if (!confirm("Delete this fact?")) return;
      await fetch(`/api/facts/${id}`, { method: "DELETE" });
      refreshFacts();
    });
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function refreshFacts() {
  const q = filterQ.value.trim();
  const cat = filterCat.value;
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (cat) params.set("category", cat);
  const res = await fetch("/api/facts?" + params.toString());
  const facts = await res.json();
  renderFacts(facts);
  // refresh category dropdown if needed
  refreshCategories();
}

async function refreshCategories() {
  const res = await fetch("/api/summary");
  const s = await res.json();
  summaryEl.innerHTML = `<b>${s.total_facts}</b> facts · ${s.categories.length} categories`;
  const wanted = new Set(s.categories);
  for (const c of wanted) {
    if (![...filterCat.options].some((o) => o.value === c)) {
      const opt = document.createElement("option");
      opt.value = c; opt.textContent = c;
      filterCat.appendChild(opt);
    }
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  addBubble(text, "user");
  input.value = "";
  input.disabled = true;
  form.querySelector("button").disabled = true;
  addBubble("Thinking…", "sys");
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, session_id: SESSION_ID }),
    });
    const data = await res.json();
    // replace the "Thinking…" bubble
    const bubbles = messagesEl.querySelectorAll(".bubble.sys");
    const last = bubbles[bubbles.length - 1];
    if (last) last.remove();

    const intent = data.intent;
    if (intent === "vent") {
      addAnswerBubble(data.answer, [], "vent");
    } else if (intent === "question") {
      addAnswerBubble(data.answer, data.citations || [], "question");
    } else {
      // fact or feeling (both stored)
      const label = intent === "feeling" ? "feeling" : "fact";
      addCapturedBubble(data.facts || [], label);
      if (data.answer) {
        // The conversational reply is shown WITHOUT an intent badge — it's just Jeeves talking.
        addAnswerBubble(data.answer, data.citations || [], null);
      }
    }
    // surface the rolling conversation topic so the user sees Jeeves is following the thread
    const topicEl = document.getElementById("topic-chip");
    if (topicEl && data.topic) topicEl.textContent = "Topic: " + data.topic;
    await refreshFacts();
  } catch (err) {
    addBubble("Error: " + err.message, "sys");
  } finally {
    input.disabled = false;
    form.querySelector("button").disabled = false;
    input.focus();
  }
});

filterQ.addEventListener("input", debounce(refreshFacts, 250));
filterCat.addEventListener("change", refreshFacts);

// --- Bulk delete ---
const deleteSelectedBtn = document.getElementById("delete-selected");
const deleteAllBtn = document.getElementById("delete-all");

function selectedIds() {
  return [...factsList.querySelectorAll(".fact-check:checked")].map(c => c.getAttribute("data-id"));
}
function syncBulkBar() {
  deleteSelectedBtn.disabled = selectedIds().length === 0;
  deleteSelectedBtn.textContent = `Delete selected (${selectedIds().length})`;
}
// Re-sync the bulk bar whenever facts re-render (checkboxes are recreated each render).
const _origRender = renderFacts;
renderFacts = function (facts) {
  _origRender(facts);
  syncBulkBar();
};
// Delegate checkbox changes (cards are rebuilt on every refresh).
factsList.addEventListener("change", (e) => {
  if (e.target.classList.contains("fact-check")) syncBulkBar();
});

deleteSelectedBtn.addEventListener("click", async () => {
  const ids = selectedIds();
  if (!ids.length) return;
  if (!confirm(`Delete ${ids.length} selected fact(s)?`)) return;
  for (const id of ids) {
    await fetch(`/api/facts/${id}`, { method: "DELETE" });
  }
  refreshFacts();
});

deleteAllBtn.addEventListener("click", async () => {
  const q = filterQ.value.trim();
  const cat = filterCat.value;
  const scope = cat ? `in "${cat}"` : (q ? `matching "${q}"` : "ALL");
  if (!confirm(`Delete ${scope} facts? This cannot be undone.`)) return;
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (cat) params.set("category", cat);
  const res = await fetch("/api/facts?" + params.toString(), { method: "DELETE" });
  const data = await res.json();
  refreshFacts();
});

function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

// initial load
refreshFacts();
