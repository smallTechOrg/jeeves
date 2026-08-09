"use strict";

const messagesEl = document.getElementById("messages");
const form = document.getElementById("msg-form");
const input = document.getElementById("msg-input");
const factsList = document.getElementById("facts-list");
const filterQ = document.getElementById("filter-q");
const filterCat = document.getElementById("filter-cat");
const summaryEl = document.getElementById("summary");

function addBubble(text, kind) {
  const b = document.createElement("div");
  b.className = "bubble " + (kind || "sys");
  b.textContent = text;
  messagesEl.appendChild(b);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function addAnswerBubble(answer, citations) {
  const b = document.createElement("div");
  b.className = "bubble answer";
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
    card.className = "fact";
    const conf = Math.round((f.confidence || 0) * 100);
    const confCls = conf >= 60 ? "hi" : "lo";
    const ent = f.entity ? `<span class="ent">· ${escapeHtml(f.entity)}</span>` : "";
    card.innerHTML =
      `<div class="meta">` +
        `<span class="cat">${escapeHtml(f.category)}</span>` +
        ent +
        `<span class="conf ${confCls}">${conf}% sure</span>` +
      `</div>` +
      `<div class="txt">${escapeHtml(f.fact_text)}</div>`;
    factsList.appendChild(card);
  }
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
  addBubble("Capturing…", "sys");
  try {
    const res = await fetch("/api/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const data = await res.json();
    // replace the "Capturing…" bubble with a result summary
    const bubbles = messagesEl.querySelectorAll(".bubble.sys");
    const last = bubbles[bubbles.length - 1];
    if (last) last.remove();
    const n = (data.facts || []).length;
    addBubble(
      `Captured ${n} fact${n === 1 ? "" : "s"}` +
      (data.stored_in_mem0 ? "." : " (semantic store unavailable — kept in local DB)."),
      "sys"
    );
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

// --- Ask Valet ---
const askInput = document.getElementById("ask-input");
const askBtn = document.getElementById("ask-btn");

async function doAsk() {
  const q = askInput.value.trim();
  if (!q) return;
  addBubble(q, "user");
  askInput.value = "";
  askBtn.disabled = true;
  askInput.disabled = true;
  addBubble("Thinking…", "sys");
  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    const data = await res.json();
    const bubbles = messagesEl.querySelectorAll(".bubble.sys");
    const last = bubbles[bubbles.length - 1];
    if (last) last.remove();
    addAnswerBubble(data.answer, data.citations || []);
  } catch (err) {
    addBubble("Error: " + err.message, "sys");
  } finally {
    askBtn.disabled = false;
    askInput.disabled = false;
    askInput.focus();
  }
}
askBtn.addEventListener("click", doAsk);
askInput.addEventListener("keydown", (e) => { if (e.key === "Enter") doAsk(); });

function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

// initial load
refreshFacts();
