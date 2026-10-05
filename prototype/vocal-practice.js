const SETS = {
  reset: [
    [2, "Pause and observe", "Name today’s ease, discomfort, and energy before loading the voice.", "self-check"],
    [4, "Quiet mental rehearsal", "Listen to or imagine one short phrase; mark breath, rhythm, and text without vocal demand.", "repertoire context"],
    [4, "Easy familiar pattern", "Only if it feels comfortable: use one familiar, low-demand pattern in the middle range.", "response check"]
  ],
  pitch: [
    [3, "Gentle arrival", "Use a familiar, easy central-range hum or lip trill and observe ease.", "onset / readiness"],
    [5, "Hear → sing → check", "Use a piano, guitar, or reference tone for short 3–5-note patterns. One calm correction is enough.", "pitch clarity"],
    [5, "Phrase with reference", "Sing one short phrase with a pitch reference, then once without it.", "transfer"],
    [2, "Close and note", "Record perceived ease and one observation before stopping.", "self-monitoring"]
  ],
  transition: [
    [3, "Gentle arrival", "Begin with a familiar central-range hum or lip trill.", "readiness"],
    [5, "Small comfortable glides", "Use a known semi-occluded exercise or teacher-approved glide without testing extremes.", "registration"],
    [5, "Short phrase transfer", "Choose a phrase that crosses a familiar transition area at an easy-to-moderate dynamic.", "repeatability"],
    [2, "Close and note", "Finish with an easy pattern or quiet mental rehearsal.", "response check"]
  ],
  phrase: [
    [3, "Gentle arrival", "Start with a comfortable familiar pattern; do not use it to test range.", "readiness"],
    [4, "Rhythm and text", "Speak or lightly sing the phrase with its rhythm before full delivery.", "phrasing"],
    [7, "Two comparable attempts", "Sing one short phrase twice at the same general demand; rate ease, pitch, and continuity.", "repertoire transfer"],
    [2, "Close and note", "Stop adding demand and record the response.", "self-monitoring"]
  ]
};

const STYLE_COPY = {
  mpb_jazz: "Use a phrase where line, lyric, and subtle rhythmic placement matter.",
  ccm: "Use a phrase from current contemporary repertoire at a comfortable, clear intensity.",
  acoustic: "Use a phrase where text and intimate delivery can remain easy and clear."
};

const KNOWLEDGE_BASIS = {
  reset: "The safety-first fallback is a local guardrail. It avoids turning healthy-singer warm-up evidence into advice for pain or sudden voice change.",
  pitch: "Pitch work uses short hear–sing–check and phrase-transfer tasks. Local Knowledge treats vocal-motor pitch control and repertoire transfer as musical practice targets, not a diagnosis.",
  transition: "A familiar, comfortable semi-occluded or teacher-approved glide is one option. Local reviews show varied immediate SOVTE findings and do not establish a universal exercise, dose, or long-term effect.",
  phrase: "The phrase route combines rhythm/text preparation, comparable attempts, and reflection. It treats repertoire transfer and self-observation as practice structure, not automatic progression."
};

const $ = selector => document.querySelector(selector);
let routine = null;
let session = null;

function buildRoutine(data) {
  const route = data.voice === "red" || data.voice === "limited" || data.energy === "low" ? "reset" : data.focus;
  const available = Number(data.time);
  let used = 0;
  const blocks = SETS[route].flatMap(([planned, title, description, target]) => {
    if (used >= available) return [];
    const minutes = Math.min(planned, available - used);
    used += minutes;
    return minutes ? [{ minutes, title, description, target }] : [];
  });
  if (used < available) {
    blocks.push({
      minutes: available - used,
      title: route === "reset" ? "Listening and score study" : "Listening, notes, and mental rehearsal",
      description: route === "reset" ? "Map rhythm, lyric, and breath choices without extra vocal loading." : "Listen back, mark one observation, or rehearse the phrase silently. Extra time does not add range or intensity.",
      target: "integration"
    });
  }
  return { route, blocks, total: available, styleCopy: STYLE_COPY[data.style], data };
}

function createElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

function renderRoutine(nextRoutine) {
  routine = nextRoutine;
  const { data, route, blocks, total, styleCopy } = routine;
  $("#routine-title").textContent = route === "reset" ? "A low-demand check-in set" : `A ${data.focus.replace("transition", "smooth-transition")} set for today`;
  $("#routine-summary").textContent = route === "reset" ? "Your answers point to a reduced or deferred vocal-load day. Stop if discomfort, pain, or worsening symptoms are present." : `This ${total}-minute set serves one current focus, then checks it in a short phrase. ${styleCopy}`;
  const tags = $("#routine-tags"); tags.replaceChildren();
  [data.time + " min", data.voice, data.focus, data.energy, data.style.replace("_", " / ")].forEach(value => tags.append(createElement("span", "", value)));
  const list = $("#routine-list"); list.replaceChildren();
  blocks.forEach((block, index) => {
    const item = createElement("article", "routine-block");
    item.append(createElement("div", "routine-block__time", `${block.minutes}m`));
    const copy = document.createElement("div");
    copy.append(createElement("p", "eyebrow", `BLOCK ${String(index + 1).padStart(2, "0")}`));
    copy.append(createElement("h3", "", block.title));
    copy.append(createElement("p", "", block.description));
    item.append(copy, createElement("div", "routine-block__target", block.target));
    list.append(item);
  });
  $("#rule-note").textContent = route === "reset" ? "Pain or a sudden substantial voice change always overrides the selected focus. Limited voice state or low energy selects a low-demand set." : "Clear/steady current state selects the requested focus. Time only trims or adds a non-progressive transfer block; it never raises intensity.";
  $("#knowledge-note").textContent = KNOWLEDGE_BASIS[route];
  $("#routine").hidden = false;
  $("#session").hidden = true;
  $("#session-summary").hidden = true;
  $("#routine").scrollIntoView({ behavior: "smooth", block: "start" });
}

function selectedValues() {
  return Object.fromEntries(new FormData($("#setup-form")));
}

function setStep(number) {
  document.querySelectorAll(".check-in-step").forEach(section => { section.hidden = Number(section.dataset.step) !== number; });
  $("#step-indicator").textContent = `Step ${number} of 2`;
  $("#check-in").scrollIntoView({ behavior: "smooth", block: "start" });
}

function validStep(names) {
  return names.every(name => document.querySelector(`input[name="${name}"]:checked`));
}

function formatTime(seconds) {
  const safe = Math.max(0, Math.ceil(seconds));
  return `${String(Math.floor(safe / 60)).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
}

function stopTimer() {
  if (session?.interval) clearInterval(session.interval);
  if (session) session.interval = null;
}

function renderBlock() {
  const block = routine.blocks[session.index];
  $("#session-progress").textContent = `BLOCK ${session.index + 1} OF ${routine.blocks.length}`;
  $("#session-title").textContent = block.title;
  $("#session-description").textContent = block.description;
  $("#session-target").textContent = `Focus: ${block.target}`;
  $("#timer").textContent = formatTime(session.remaining);
  $("#timer-status").textContent = "Ready when you are.";
  $("#timer-start").disabled = false;
  $("#timer-pause").disabled = true;
}

function tick() {
  session.remaining = Math.max(0, (session.deadline - Date.now()) / 1000);
  $("#timer").textContent = formatTime(session.remaining);
  if (session.remaining === 0) {
    stopTimer();
    $("#timer-status").textContent = "Time is up. Complete or skip this block when you are ready.";
    $("#timer-start").disabled = true;
    $("#timer-pause").disabled = true;
  }
}

function startTimer() {
  if (!session || session.remaining <= 0) return;
  session.deadline = Date.now() + session.remaining * 1000;
  session.interval = setInterval(tick, 250);
  $("#timer-status").textContent = "Timer running. Advance manually when the block is complete.";
  $("#timer-start").disabled = true;
  $("#timer-pause").disabled = false;
}

function pauseTimer() {
  if (!session?.interval) return;
  tick(); stopTimer();
  $("#timer-status").textContent = "Timer paused.";
  $("#timer-start").disabled = session.remaining <= 0;
  $("#timer-pause").disabled = true;
}

function finishSession() {
  stopTimer();
  const completed = session.completed.filter(item => item === "complete").length;
  const skipped = session.completed.filter(item => item === "skip").length;
  $("#summary-copy").textContent = `You completed ${completed} of ${routine.blocks.length} block${routine.blocks.length === 1 ? "" : "s"}${skipped ? ` and skipped ${skipped}` : ""}. Keep only what was useful today.`;
  $("#session").hidden = true;
  $("#session-summary").hidden = false;
  $("#session-summary").scrollIntoView({ behavior: "smooth", block: "start" });
}

function advance(kind) {
  stopTimer();
  session.completed.push(kind);
  session.index += 1;
  if (session.index >= routine.blocks.length) return finishSession();
  session.remaining = routine.blocks[session.index].minutes * 60;
  renderBlock();
}

$("#next-step").addEventListener("click", () => {
  if (!validStep(["time", "voice", "energy"])) { $("#step-indicator").textContent = "Choose all three readiness options to continue."; return; }
  setStep(2);
});
$("#previous-step").addEventListener("click", () => setStep(1));
$("#setup-form").addEventListener("submit", event => {
  event.preventDefault();
  if (!validStep(["focus", "style"])) return;
  renderRoutine(buildRoutine(selectedValues()));
});
$("#edit-check-in").addEventListener("click", () => { $("#routine").hidden = true; setStep(1); });
$("#start-session").addEventListener("click", () => {
  session = { index: 0, completed: [], remaining: routine.blocks[0].minutes * 60, interval: null, deadline: null };
  renderBlock(); $("#session").hidden = false; $("#session").scrollIntoView({ behavior: "smooth", block: "start" });
});
$("#timer-start").addEventListener("click", startTimer);
$("#timer-pause").addEventListener("click", pauseTimer);
$("#timer-restart").addEventListener("click", () => { pauseTimer(); session.remaining = routine.blocks[session.index].minutes * 60; renderBlock(); });
$("#complete-block").addEventListener("click", () => advance("complete"));
$("#skip-block").addEventListener("click", () => advance("skip"));
$("#end-session").addEventListener("click", finishSession);
$("#new-session").addEventListener("click", () => { stopTimer(); session = null; routine = null; $("#setup-form").reset(); $("#routine").hidden = true; $("#session-summary").hidden = true; $("#reflection").value = ""; setStep(1); });
