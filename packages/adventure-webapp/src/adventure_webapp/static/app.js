// Adventure SPA -- single-scene loop: select -> roll -> narrate
const $ = (id) => document.getElementById(id);
let gameId = null;
let autoTimer = null;
let templates = [];
let lastGame = null;

async function fetchJSON(url, opts) {
  const res = await fetch(url, {headers: {"Content-Type":"application/json"}, ...opts});
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = {raw:text}; }
  if (!res.ok) throw new Error((data && data.detail) || res.statusText);
  return data;
}

function esc(s){ return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

function outcomePill(outcome){
  const cls = outcome==="success"?"success": outcome==="critical"?"critical": outcome==="partial"?"partial": outcome==="failure"?"failure":"";
  return `<span class="pill ${cls}">${esc(outcome||"")}</span>`;
}

async function loadTemplates(){
  const data = await fetchJSON("/api/templates");
  templates = data;
  const sel = $("template");
  sel.innerHTML = data.map(t=>`<option value="${t.template_id}">${t.title} — ${t.objective.slice(0,54)}</option>`).join("");
  sel.addEventListener("change", renderTemplateMeta);
  renderTemplateMeta();
}
function renderTemplateMeta(){
  const tid = $("template").value;
  const t = templates.find(x=>x.template_id===tid);
  if(!t) return;
  $("template-meta").textContent = `${t.location||""} · ${t.threat||""} · ${t.segments} segments · ${t.beats.length} beats`;
  $("template-desc").textContent = `${t.objective} — beats: ${t.beats.join(" → ")}`;
}

async function startScene(){
  const template_id = $("template").value;
  const actor = $("actor").value.trim() || "Elaria";
  const seed = $("seed").value ? parseInt($("seed").value,10) : null;
  const btn = $("btn-start");
  btn.disabled = true; btn.textContent = "Starting...";
  try {
    const data = await fetchJSON("/api/games", {method:"POST", body: JSON.stringify({template_id, actor, seed})});
    gameId = data.game_id;
    lastGame = data;
    $("game-id").textContent = gameId;
    $("play").style.display = "";
    $("story-sec").style.display = "";
    $("btn-restart").style.display = "";
    $("setup-pill").textContent = data.scene.title;
    $("scene-title").textContent = data.scene.title;
    $("scene-objective").textContent = data.scene.objective;
    renderGame(data);
  } catch(e){
    alert("Start failed: "+e.message);
  } finally { btn.disabled=false; btn.textContent="Start scene"; }
}

function renderGame(g){
  lastGame = g;
  const clock = g.clock || {ticks:0, segments:6, completed:false};
  const pct = clock.segments ? Math.round(100*clock.ticks/clock.segments) : 0;
  $("clock-fill").style.width = pct+"%";
  $("clock-label").textContent = `${clock.name||"progress"} ${clock.ticks}/${clock.segments}`;
  $("clock-pill").textContent = `${clock.ticks}/${clock.segments}${clock.completed?" ✓":""}`;
  $("status-pill").textContent = g.completed ? "resolved" : "active";
  $("status-pill").className = "pill " + (g.completed ? "accent" : "");
  $("story-pill").textContent = `${g.turns.length} turns${g.completed?" · completed":""}`;
  renderTurnArea(g);
  renderStory(g);
  $("debug").style.display = "";
  $("debug-pre").textContent = JSON.stringify(g, null, 2);
  if(g.completed){
    stopAuto();
    $("turn-area").insertAdjacentHTML("beforeend", `<div class="empty" style="margin-top:12px">Scene resolved — story below is the full arc. Toggle choices/rolls or start a new scene.</div>`);
  } else if($("auto").checked){
    scheduleAuto();
  }
}

function renderTurnArea(g){
  const pending = g.pending;
  const box = $("turn-area");
  if(g.completed){
    box.innerHTML = `<div class="turn done"><div class="small muted">All beats played — clock completed.</div></div>`;
    return;
  }
  if(!pending){
    box.innerHTML = `<div class="empty">No pending turn — advancing...</div>`;
    return;
  }
  const choices = pending.choices||{};
  const showRolls = $("show-rolls").checked;
  // Build 3 cards
  const cards = ["obvious","option","odd"].map(cat=>{
    const txt = choices[cat]||"";
    const label = cat + (cat==="obvious"?" · safe":"") + (cat==="odd"?" · wild":"");
    return `<div class="choice-card" data-pick="${cat}" onclick="pick('${cat}')">
      <div class="label">${esc(label)} <span class="pill" style="float:right">pick</span></div>
      <div>${esc(txt)}</div>
      <div class="small muted" style="margin-top:6px">${esc(pending.position)}/${esc(pending.effect)}</div>
    </div>`;
  }).join("");
  box.innerHTML = `
    <div class="turn pending">
      <div class="small muted">Beat ${pending.beat_idx+1}: ${esc(pending.beat_title)} · seq ${pending.seq}</div>
      <div style="font-weight:700;margin:4px 0">${esc(pending.situation)}</div>
      <div class="choice-grid">${cards}</div>
      <div class="small muted">Pick one — the tool then rolls <code>action_roll</code> (1d6 pool). Even the obvious 4-6 can be a <em>partial</em> or <em>failure</em> if the die is low. ${showRolls?"Outcome + ticks appear in Story.":""}</div>
      <div class="controls" style="margin-top:10px">
        <button class="ghost" onclick="autoOnce()">Auto pick via Triple-O 1d6</button>
        <span class="small muted">Auto distribution: 4-6 obvious, 2-3 option, 1 odd.</span>
      </div>
    </div>
  `;
}

function renderStory(g){
  const showOffered = $("toggle-choices").checked;
  const showChosen = $("toggle-chosen").checked;
  const showOutcome = $("toggle-rolls").checked;
  const hideNonChosen = document.body.dataset.hideNonChosen === "1";
  const container = $("story");
  if(!g.turns.length){
    container.innerHTML = `<span class="muted">Story will appear beat by beat — choices are offered then the die resolves them.</span>`;
    $("timeline").innerHTML = "";
    return;
  }
  // Main story prose
  let html = "";
  g.turns.forEach(t=>{
    if(!t.narration && !t.picked) return; // pending not yet played
    const outcome = t.roll ? t.roll.outcome : null;
    const ticks = t.roll ? t.roll.ticks : null;
    const rolls = t.roll ? (t.roll.rolls||[]) : [];
    const cons = t.roll ? (t.roll.consequence||[]) : [];
    html += `<div style="margin:8px 0;padding:8px 10px;border:1px solid var(--border);border-radius:8px;background:#fff">`;
    html += `<div class="small muted">Beat ${t.beat_idx+1} · ${esc(t.beat_title)} ${t.roll ? outcomePill(outcome) : ""} ${ticks!=null?`<span class="pill">ticks ${ticks} [${rolls.join(",")}]</span>`:""}</div>`;
    if(t.narration) html += `<div style="margin:6px 0">${esc(t.narration)}</div>`;
    if(showOffered){
      html += `<div class="choice-grid" style="margin-top:8px">`;
      ["obvious","option","odd"].forEach(cat=>{
        if(hideNonChosen && t.picked && cat!==t.picked) return;
        const txt = (t.choices||{})[cat]||"";
        const isChosen = t.picked===cat;
        const cls = "choice-card " + (isChosen && showChosen ? "chosen" : isChosen ? "" : "dim");
        const badge = isChosen ? ` <span class="pill chosen">chosen</span>` : "";
        html += `<div class="${cls}" style="cursor:default"><div class="label">${esc(cat)}${badge}</div><div class="small">${esc(txt)}</div></div>`;
      });
      html += `</div>`;
    } else if(t.picked){
      html += `<div class="small" style="margin-top:6px"><span class="pill chosen">${esc(t.picked)} chosen</span> ${esc(t.pick_text||"")}</div>`;
    }
    if(showOutcome && t.roll){
      const consTxt = cons.length ? ` — ${esc(cons.slice(0,2).join("; "))}` : "";
      html += `<div class="small muted" style="margin-top:6px">Roll: ${outcomePill(outcome)} rolls [${rolls.join(", ")}] pool ${t.roll.pool} ${esc(t.roll.position)}/${esc(t.roll.effect)} ticks ${ticks}${consTxt}</div>`;
    }
    html += `</div>`;
  });
  container.innerHTML = html || `<span class="muted">—</span>`;

  // Compact timeline below story
  const tl = $("timeline");
  tl.innerHTML = `<div class="small muted">Timeline — every beat is traversable (like fused's JSONL). Click a beat to see its payload.</div>` + g.turns.map(t=>{
    const isPending = !t.picked;
    return `<div class="turn ${isPending?"pending":"done"}" style="padding:8px 10px">
      <div class="small muted">#${t.seq} · ${esc(t.beat_title)} ${isPending?'<span class="pill">pending</span>': outcomePill(t.roll? t.roll.outcome:"")}</div>
      ${t.picked? `<div class="small"><b>Picked ${esc(t.picked)}:</b> ${esc(t.pick_text||"")} ${t.roll?`→ ${esc(t.roll.outcome)}`:""}</div>` : `<div class="small muted">Awaiting pick…</div>`}
      ${t.narration? `<div class="small" style="margin-top:4px">${esc(t.narration.slice(0,180))}</div>`:""}
    </div>`;
  }).join("");
}

window.pick = async function(cat){
  if(!gameId) return;
  const cards = document.querySelectorAll(".choice-card[data-pick]");
  cards.forEach(c=>c.style.pointerEvents="none");
  try {
    const data = await fetchJSON(`/api/games/${gameId}/choose`, {method:"POST", body: JSON.stringify({pick:cat})});
    // data contains {turn,next_turn,clock,game}
    const g = data.game || data;
    renderGame(g);
  } catch(e){
    alert("Pick failed: "+e.message);
    cards.forEach(c=>c.style.pointerEvents="");
  }
};

window.autoOnce = async function(){
  if(!gameId) return;
  try {
    const data = await fetchJSON(`/api/games/${gameId}/auto`, {method:"POST", body: JSON.stringify({})});
    renderGame(data.game || data);
  } catch(e){ alert("Auto failed: "+e.message); }
};

function scheduleAuto(){
  stopAuto();
  if(!gameId || !lastGame || lastGame.completed) return;
  const delay = parseInt($("auto-delay").value,10)||1400;
  autoTimer = setTimeout(async ()=>{
    if(!gameId || !$("auto").checked) return;
    await autoOnce();
    if(lastGame && !lastGame.completed && $("auto").checked) scheduleAuto();
  }, delay);
}
function stopAuto(){ if(autoTimer){ clearTimeout(autoTimer); autoTimer=null; } }

$("btn-start").addEventListener("click", startScene);
$("btn-restart").addEventListener("click", ()=>{ stopAuto(); gameId=null; lastGame=null; $("play").style.display="none"; $("story-sec").style.display="none"; $("turn-area").innerHTML=""; $("story").innerHTML=""; });
$("auto").addEventListener("change", ()=>{ if($("auto").checked) scheduleAuto(); else stopAuto(); });
$("auto-delay").addEventListener("change", ()=>{ if($("auto").checked) scheduleAuto(); });
["toggle-choices","toggle-chosen","toggle-rolls","show-rolls","btn-hide-choices"].forEach(id=>{
  const el = $(id);
  if(!el) return;
  if(el.id==="btn-hide-choices"){
    el.addEventListener("click", ()=>{
      document.body.dataset.hideNonChosen = document.body.dataset.hideNonChosen==="1" ? "0":"1";
      el.textContent = document.body.dataset.hideNonChosen==="1" ? "Show all options" : "Hide non-chosen";
      if(lastGame) renderStory(lastGame);
    });
  } else {
    el.addEventListener("change", ()=>{ if(lastGame){ renderGame(lastGame); } });
  }
});
$("btn-copy").addEventListener("click", ()=>{
  const txt = $("story").innerText || "";
  navigator.clipboard.writeText(txt).then(()=>{ $("btn-copy").textContent="Copied"; setTimeout(()=>$("btn-copy").textContent="Copy story",1200); });
});

// init
loadTemplates();
