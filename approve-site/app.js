// NEYĒN Brain · approval page. Public values only (project URL + publishable key are designed to be visible).
// Who may approve is decided on the server: brain-api /ana/* checks Ana's Auth user id and confirmed email.
// Login = 6-digit email code (no tokens in URLs, no redirects). Session lives in memory only: closing the tab signs out.
"use strict";
const SUPABASE_URL = "https://gsmtzdramqzcqdywboro.supabase.co";
const PUBLISHABLE_KEY = "sb_publishable_RgvJSpceqRsmzhZpmcUsLg_ObGRl7fY";
const API = SUPABASE_URL + "/functions/v1/brain-api/ana";

const memory = new Map();
const memoryStorage = { getItem: (k) => (memory.has(k) ? memory.get(k) : null), setItem: (k, v) => { memory.set(k, v); }, removeItem: (k) => { memory.delete(k); } };
const sb = supabase.createClient(SUPABASE_URL, PUBLISHABLE_KEY, {
  auth: { persistSession: false, storage: memoryStorage, autoRefreshToken: true, detectSessionInUrl: false },
});

const app = document.getElementById("app");
const el = (tag, props = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) { if (k === "class") n.className = v; else if (k === "text") n.textContent = v; else n.setAttribute(k, v); }
  for (const k of kids) if (k) n.append(k);
  return n;
};
const clear = () => { while (app.firstChild) app.removeChild(app.firstChild); };
const note = (t) => el("div", { class: "msg", text: t });

let pendingEmail = "";

function showEmail(message) {
  clear();
  if (message) app.append(note(message));
  const input = el("input", { id: "email", type: "email", autocomplete: "email", placeholder: "tu@email.com" });
  const btn = el("button", { class: "primary", text: "Enviarme un código" });
  btn.onclick = async () => {
    const email = input.value.trim();
    if (!email) return;
    btn.disabled = true;
    // shouldCreateUser:false: no new accounts are ever created from this page.
    const { error } = await sb.auth.signInWithOtp({ email, options: { shouldCreateUser: false } });
    btn.disabled = false;
    if (error) return showEmail("No se pudo enviar el código. Inténtalo de nuevo en un minuto.");
    pendingEmail = email;
    showCode();
  };
  app.append(el("label", { for: "email", text: "Tu email" }), input, btn);
}

function showCode(message) {
  clear();
  app.append(note(message || "Te hemos enviado un código de 6 cifras por email. Escríbelo aquí."));
  const input = el("input", { id: "code", inputmode: "numeric", autocomplete: "one-time-code", maxlength: "10", placeholder: "123456" });
  const btn = el("button", { class: "primary", text: "Entrar" });
  const back = el("button", { class: "ghost", text: "Cambiar email" });
  back.onclick = () => showEmail();
  btn.onclick = async () => {
    const token = input.value.replace(/\D/g, "");
    if (!token) return;
    btn.disabled = true;
    const { error } = await sb.auth.verifyOtp({ email: pendingEmail, token, type: "email" });
    btn.disabled = false;
    if (error) return showCode("Código incorrecto o caducado. Pide otro si hace falta.");
    showPending();
  };
  app.append(el("label", { for: "code", text: "Código" }), input, el("div", { class: "actions" }, btn, back));
}

async function call(path, opts = {}) {
  const { data: { session } } = await sb.auth.getSession();
  if (!session) { const e = new Error("sign in"); e.status = 401; throw e; }
  let r;
  try {
    r = await fetch(API + path, { ...opts, cache: "no-store", headers: { "Authorization": "Bearer " + session.access_token, "Content-Type": "application/json" } });
  } catch { const e = new Error("network"); e.status = 0; throw e; }
  let j = null;
  try { j = await r.json(); } catch { /* unknown body */ }
  if (!r.ok) { const e = new Error((j && j.error) || "error"); e.status = r.status; throw e; }
  return j;
}

async function signOut(message) { await sb.auth.signOut(); memory.clear(); showEmail(message); }

async function showPending(message) {
  clear();
  app.append(note("Cargando…"));
  let res;
  try { res = await call("/pending"); }
  catch (e) {
    if (e.status === 401) return signOut("Vuelve a entrar.");
    if (e.status === 403) return signOut("Esta cuenta no puede aprobar.");
    clear(); app.append(note("No se pudo cargar la lista. Recarga la página.")); return;
  }
  if (!res || !Array.isArray(res.items)) { clear(); app.append(note("Respuesta inesperada del servidor. Recarga la página.")); return; }
  const items = res.items;
  clear();
  if (message) app.append(note(message));
  const out = el("button", { class: "ghost", text: "Salir" });
  out.onclick = () => signOut("Has salido.");
  const countText = res.total > res.shown
    ? "Mostrando las " + res.shown + " más recientes de " + res.total + " pendientes. Decide estas y recarga para ver las siguientes."
    : res.total + " propuesta(s) pendiente(s)";
  app.append(el("div", { class: "actions" }, el("span", { class: "sub", text: countText }), out));
  if (!items.length) { app.append(note("No hay nada pendiente.")); return; }
  for (const i of items) app.append(card(i));
}

const ORIGIN_LABEL = { ai_interpretation: "Interpretación de una IA", human: "Aportación humana", source_material: "Material original" };

// Source line: a clickable link only for https URLs (opened without referrer); anything else is shown as plain text.
function sourceLine(src) {
  if (!src || (!src.title && !src.uri)) return el("div", { class: "meta warn", text: "Fuente: sin fuente registrada." });
  const line = el("div", { class: "meta", text: "Fuente: " + (src.title || "(sin título)") + " " });
  let safe = null;
  try { const u = new URL(src.uri || ""); if (u.protocol === "https:") safe = u.href; } catch { /* not a URL */ }
  if (safe) line.append(el("a", { href: safe, target: "_blank", rel: "noopener noreferrer", text: "abrir" }));
  else if (src.uri) line.append(el("span", { text: "(referencia interna: " + src.uri + ")" }));
  else line.append(el("span", { text: "(sin enlace)" }));
  return line;
}

function card(i) {
  const meta = [i.project, i.kind, "propuesto por " + (i.by || "?"), (i.created_at || "").slice(0, 10), "versión " + i.version].join(" · ");
  const ok = el("button", { class: "ok", text: "Aprobar" });
  const no = el("button", { class: "no", text: "Rechazar" });
  const status = el("span");
  const actions = el("div", { class: "actions" }, ok, no, status);
  const c = el("div", { class: "card" },
    el("div", { class: "meta", text: meta }),
    el("div", { class: "meta", text: "Tipo: " + (ORIGIN_LABEL[i.origin] || i.origin || "desconocido") + " · Comprobado: " + (i.verification === "verified" ? "sí" : i.verification === "disputed" ? "en disputa" : "no") }),
    el("p", { class: "title", text: i.title }),
    el("div", { class: "body", text: i.body || "(sin texto)" }),
    sourceLine(i.source),
    actions);
  const send = async (decision) => {
    if (!confirm(decision === "approve" ? "¿Aprobar este ítem?" : "¿Rechazar este ítem?")) return;
    ok.disabled = true; no.disabled = true; status.textContent = "Guardando…";
    try {
      const r = await call("/items/" + encodeURIComponent(i.id) + "/decide", { method: "POST", body: JSON.stringify({ decision, version: i.version }) });
      if (r && (r.status === "approved" || r.status === "rejected")) {
        c.classList.add("done");
        while (actions.firstChild) actions.removeChild(actions.firstChild);
        actions.append(el("span", { text: r.status === "approved" ? "✓ Aprobado" : "✗ Rechazado" }));
      } else {
        // Unknown answer: never assume an outcome; reload the real state.
        showPending("Respuesta inesperada. He recargado la lista para mostrar el estado real.");
      }
    } catch (e) {
      if (e.status === 401) return signOut("Vuelve a entrar.");
      if (e.status === 409) return showPending("Ese ítem cambió o ya estaba decidido. Lista recargada.");
      // Network or server error: the outcome is unknown, so reload instead of guessing.
      showPending("No se pudo confirmar la decisión. He recargado la lista para mostrar el estado real.");
    }
  };
  ok.onclick = () => send("approve");
  no.onclick = () => send("reject");
  return c;
}

showEmail();
