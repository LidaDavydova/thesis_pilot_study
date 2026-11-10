'use strict';

const TYPE_LABELS = {
  identify_bug: 'Find the bug',
  check_spec: 'Check the specification',
  select_impl: 'Select an implementation',
};

const state = {
  session: null,
  trialIndex: 0,
  trial: null,
  task: null,
  phase: 'welcome',
  initialAnswer: null,
  confidence: 50,
  recommendation: null,
  evidence: [],
  evidenceAvailable: false,
  panelOpen: false,
  evidenceActiveMs: 0,
  focusLostMs: 0,
  maxBlurMs: 0,
  inactiveSince: null,
  lastTick: null,
  interactionCount: 0,
  lastScrollLog: 0,
};

document.addEventListener('DOMContentLoaded', init);

function init() {
  setInterval(tick, 250);
  window.addEventListener('blur', onFocusChange);
  window.addEventListener('focus', onFocusChange);
  document.addEventListener('visibilitychange', onFocusChange);
  renderWelcome();
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body && body.detail) message = body.detail;
    } catch (_) {
      // Keep the status message.
    }
    throw new Error(message);
  }
  return response.json();
}

function esc(value) {
  return String(value == null ? '' : value).replace(/[&<>"']/g, (char) => {
    switch (char) {
      case '&': return '&amp;';
      case '<': return '&lt;';
      case '>': return '&gt;';
      case '"': return '&quot;';
      case "'": return '&#39;';
      default: return char;
    }
  });
}

function setPhase(phase) {
  state.phase = phase;
  state.lastTick = performance.now();
}

function isInactive() {
  return !document.hasFocus() || document.visibilityState === 'hidden';
}

function onFocusChange() {
  if (!state.session) return;
  if (isInactive()) {
    if (!state.inactiveSince) {
      state.inactiveSince = performance.now();
      logEvent('focus_lost');
    }
  } else if (state.inactiveSince) {
    const duration = performance.now() - state.inactiveSince;
    state.maxBlurMs = Math.max(state.maxBlurMs, duration);
    state.inactiveSince = null;
    logEvent('focus_gained', { duration_ms: Math.round(duration) });
  }
}

function tick() {
  const now = performance.now();
  if (state.lastTick == null) {
    state.lastTick = now;
    return;
  }
  const dt = Math.max(0, now - state.lastTick);
  state.lastTick = now;
  if (state.phase !== 'recommendation' && state.phase !== 'final') return;

  if (isInactive()) {
    if (!state.inactiveSince) state.inactiveSince = now;
    state.focusLostMs += dt;
    state.maxBlurMs = Math.max(state.maxBlurMs, now - state.inactiveSince);
    return;
  }

  if (state.inactiveSince) {
    state.maxBlurMs = Math.max(state.maxBlurMs, now - state.inactiveSince);
    state.inactiveSince = null;
  }
  if (state.panelOpen) state.evidenceActiveMs += dt;
}

function logEvent(type, payload = {}) {
  if (!state.session) return;
  const sid = state.session.session_id;
  const idx = state.trialIndex == null ? 0 : state.trialIndex;
  api(`/api/session/${sid}/trial/${idx}/event`, {
    method: 'POST',
    body: JSON.stringify({
      event_type: type,
      client_time_ms: performance.now(),
      payload,
    }),
  }).catch(() => {
    // Event logging must never interrupt the participant.
  });
}

function updateProgress(completed) {
  const total = state.session ? state.session.total_trials : 0;
  const pct = total ? Math.max(0, Math.min(100, (completed / total) * 100)) : 0;
  const fill = document.getElementById('progress-fill');
  const text = document.getElementById('progress-text');
  if (fill) fill.style.width = `${pct}%`;
  if (text) {
    text.textContent = total
      ? `Task ${Math.min(completed + 1, total)} of ${total}`
      : 'Welcome';
  }
  const label = document.getElementById('session-label');
  if (label) {
    label.textContent = state.session
      ? `Session ${state.session.session_id} · ${state.session.participant_code}`
      : '';
  }
}

function resetTrialMetrics() {
  state.initialAnswer = null;
  state.confidence = 50;
  state.recommendation = null;
  state.evidence = [];
  state.evidenceAvailable = false;
  state.panelOpen = false;
  state.evidenceActiveMs = 0;
  state.focusLostMs = 0;
  state.maxBlurMs = 0;
  state.inactiveSince = isInactive() ? performance.now() : null;
  state.interactionCount = 0;
  state.lastScrollLog = 0;
  state.lastTick = performance.now();
}

function taskHeader() {
  return `
    <div class="task-header">
      <span class="badge">${esc(TYPE_LABELS[state.task.type] || state.task.type)}</span>
      <span>Task ${state.trialIndex + 1} of ${state.session.total_trials}</span>
    </div>`;
}

function codeBlock(code, numbered = true) {
  const lines = String(code || '').split('\n');
  if (!numbered) {
    return `<div class="code-block plain">${lines
      .map((line) => `<div class="code-line"><span class="code-text">${esc(line) || ' '}</span></div>`)
      .join('')}</div>`;
  }
  return `<div class="code-block">${lines
    .map(
      (line, index) => `
      <div class="code-line">
        <span class="ln">${index + 1}</span>
        <span class="code-text">${esc(line) || ' '}</span>
      </div>`,
    )
    .join('')}</div>`;
}

function answerWidgetHtml(task, initial) {
  if (task.type === 'identify_bug') {
    const hasBug = initial ? initial.has_bug : null;
    return `
      <div class="answer-options">
        <label class="answer-option">
          <input type="radio" name="has_bug" value="true" ${hasBug === true ? 'checked' : ''}>
          <span>Yes, there is a bug</span>
        </label>
        <label class="answer-option">
          <input type="radio" name="has_bug" value="false" ${hasBug === false ? 'checked' : ''}>
          <span>No, the code has no bug</span>
        </label>
      </div>
      <div id="line-wrap" style="display:${hasBug === true ? 'block' : 'none'}">
        <label for="bug-line">Line number of the bug (1–${task.line_count})</label>
        <input type="number" id="bug-line" min="1" max="${task.line_count}"
          value="${initial && initial.line != null ? esc(initial.line) : ''}">
      </div>`;
  }

  if (task.type === 'check_spec') {
    const compliant = initial ? initial.compliant : null;
    return `
      <div class="answer-options">
        <label class="answer-option">
          <input type="radio" name="compliant" value="true" ${compliant === true ? 'checked' : ''}>
          <span><strong>COMPLIANT</strong> — the implementation matches the specification</span>
        </label>
        <label class="answer-option">
          <input type="radio" name="compliant" value="false" ${compliant === false ? 'checked' : ''}>
          <span><strong>NOT COMPLIANT</strong> — the implementation violates the specification</span>
        </label>
      </div>`;
  }

  return `
    <div class="candidates">
      ${(task.candidates || [])
        .map(
          (candidate) => `
        <label class="candidate">
          <input type="radio" name="candidate" value="${esc(candidate.id)}"
            ${initial && initial.candidate === candidate.id ? 'checked' : ''}>
          <div>
            <strong>Implementation ${esc(candidate.id)}</strong>
            <div class="candidate-code">${esc(candidate.code)}</div>
          </div>
        </label>`,
        )
        .join('')}
    </div>`;
}

function attachAnswerWidget(task, initial) {
  const lineWrap = document.getElementById('line-wrap');
  if (lineWrap) {
    const update = () => {
      const selected = document.querySelector('input[name="has_bug"]:checked');
      lineWrap.style.display = selected && selected.value === 'true' ? 'block' : 'none';
    };
    document
      .querySelectorAll('input[name="has_bug"]')
      .forEach((input) => input.addEventListener('change', update));
    update();
  }
}

function collectAnswer(task) {
  if (task.type === 'identify_bug') {
    const selected = document.querySelector('input[name="has_bug"]:checked');
    if (!selected) throw new Error('Choose whether the code contains a bug.');
    const hasBug = selected.value === 'true';
    let line = null;
    if (hasBug) {
      const raw = document.getElementById('bug-line').value.trim();
      if (!raw) throw new Error('Enter the line number where the bug is located.');
      line = Number(raw);
      if (!Number.isInteger(line) || line < 1 || line > task.line_count) {
        throw new Error(`The line number must be between 1 and ${task.line_count}.`);
      }
    }
    return { has_bug: hasBug, line };
  }

  if (task.type === 'check_spec') {
    const selected = document.querySelector('input[name="compliant"]:checked');
    if (!selected) throw new Error('Choose whether the implementation is compliant.');
    return { compliant: selected.value === 'true' };
  }

  const selected = document.querySelector('input[name="candidate"]:checked');
  if (!selected) throw new Error('Select one implementation.');
  return { candidate: selected.value };
}

function summarizeAnswer(task, answer) {
  if (!answer) return 'No answer yet';
  if (task.type === 'identify_bug') {
    return answer.has_bug ? `Bug on line ${answer.line}` : 'No bug';
  }
  if (task.type === 'check_spec') {
    return answer.compliant ? 'Compliant' : 'Not compliant';
  }
  return `Implementation ${answer.candidate}`;
}

function showError(message) {
  const error = document.getElementById('error');
  if (error) {
    error.textContent = message;
    error.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  } else {
    window.alert(message);
  }
}

function setLoading() {
  document.getElementById('screen').innerHTML =
    '<section class="card"><p class="muted">Loading…</p></section>';
}

// ---------------------------------------------------------------------------
// Welcome and resume
// ---------------------------------------------------------------------------

function renderWelcome() {
  setPhase('welcome');
  state.session = null;
  state.trialIndex = 0;
  updateProgress(0);
  document.getElementById('screen').innerHTML = `
    <section class="card welcome">
      <h1>Verification support study</h1>
      <p>
        This is a pilot interface for a study on how verification evidence affects
        reliance on AI recommendations. You will complete a sequence of short Python
        tasks. For each task you give an initial answer, rate your confidence, see a
        recommendation, and then give your final answer.
      </p>
      <div class="welcome-grid">
        <div><strong>Your task</strong><span>Decide whether code contains a bug, check a specification, or choose an implementation.</span></div>
        <div><strong>Recommendations</strong><span>An AI recommendation is shown after your confidence rating. It may be right or wrong.</span></div>
        <div><strong>Verification</strong><span>When available, verification evidence can be opened and inspected before your final answer.</span></div>
      </div>
      <label for="participant-code">Participant code (optional)</label>
      <input type="text" id="participant-code" autocomplete="off" placeholder="e.g. P-001">
      <label class="checkbox-row">
        <input type="checkbox" id="dry-run">
        <span>Technical dry run: interface testing only. Do not enter research data and do not treat this as a study session.</span>
      </label>
      <div class="actions">
        <button id="start">Start session</button>
      </div>
      <div id="error" class="error"></div>
      <div id="resume-box" class="resume-box" hidden></div>
    </section>`;

  document.getElementById('start').addEventListener('click', startSession);
  offerResume();
}

async function startSession() {
  const button = document.getElementById('start');
  button.disabled = true;
  const code = document.getElementById('participant-code').value.trim();
  const mode = document.getElementById('dry-run').checked ? 'dry_run' : 'pilot';
  try {
    const session = await api('/api/session', {
      method: 'POST',
      body: JSON.stringify({ participant_code: code || null, mode }),
    });
    state.session = session;
    localStorage.setItem('pilot_session_id', session.session_id);
    logEvent('session_started', { mode });
    await loadTrial(0);
  } catch (error) {
    button.disabled = false;
    showError(error.message);
  }
}

async function offerResume() {
  const sessionId = localStorage.getItem('pilot_session_id');
  if (!sessionId) return;
  const box = document.getElementById('resume-box');
  if (!box) return;
  try {
    const session = await api(`/api/session/${sessionId}`);
    if (session.status === 'completed') {
      localStorage.removeItem('pilot_session_id');
      return;
    }
    box.hidden = false;
    box.innerHTML = `
      <p class="small muted">An unfinished session was found for ${esc(session.participant_code)}.</p>
      <button class="secondary" id="resume">Resume session</button>`;
    document.getElementById('resume').addEventListener('click', () => {
      state.session = {
        session_id: session.session_id,
        participant_code: session.participant_code,
        mode: session.mode,
        total_trials: session.total_trials,
      };
      const next = session.next_trial_index;
      if (next == null) {
        renderCompletion();
      } else {
        loadTrial(next);
      }
    });
  } catch (_) {
    localStorage.removeItem('pilot_session_id');
  }
}

// ---------------------------------------------------------------------------
// Trial screens
// ---------------------------------------------------------------------------

async function loadTrial(index) {
  setLoading();
  const sessionId = state.session.session_id;
  try {
    const data = await api(`/api/session/${sessionId}/trial/${index}`);
    state.trialIndex = index;
    state.trial = data;
    state.task = data.task;
    resetTrialMetrics();
    updateProgress(index);

    if (data.state === 'initial_submitted') {
      state.initialAnswer = data.initial_answer;
      setPhase('confidence');
      renderConfidence();
      return;
    }
    if (data.state === 'recommendation_shown') {
      state.initialAnswer = data.initial_answer;
      state.confidence = data.confidence;
      state.recommendation = data.recommendation;
      state.evidenceAvailable = data.evidence_available;
      state.evidence = data.evidence || [];
      setPhase('recommendation');
      renderRecommendation();
      return;
    }
    if (data.state === 'final_submitted') {
      state.initialAnswer = data.initial_answer;
      renderAlreadySubmitted(data);
      return;
    }
    setPhase('task');
    renderTask();
  } catch (error) {
    document.getElementById('screen').innerHTML = `
      <section class="card">
        <h2>Could not load the trial</h2>
        <p class="muted">${esc(error.message)}</p>
        <div class="actions"><button id="back">Back to start</button></div>
      </section>`;
    document.getElementById('back').addEventListener('click', renderWelcome);
  }
}

function renderTask() {
  const task = state.task;
  const code = task.type === 'select_impl' ? '' : codeBlock(task.code);
  document.getElementById('screen').innerHTML = `
    <section class="card">
      ${taskHeader()}
      <h2>${esc(task.title)}</h2>
      <p class="prompt">${esc(task.prompt)}</p>
      ${code}
      <h3>Your answer</h3>
      <div id="answer-area">${answerWidgetHtml(task, null)}</div>
      <div class="actions">
        <button id="submit-initial">Submit initial answer</button>
      </div>
      <div id="error" class="error"></div>
    </section>`;
  attachAnswerWidget(task, null);
  document.getElementById('submit-initial').addEventListener('click', submitInitial);
}

async function submitInitial() {
  const button = document.getElementById('submit-initial');
  button.disabled = true;
  try {
    const answer = collectAnswer(state.task);
    await api(`/api/session/${state.session.session_id}/trial/${state.trialIndex}/initial`, {
      method: 'POST',
      body: JSON.stringify({ answer }),
    });
    state.initialAnswer = answer;
    logEvent('initial_submitted', { answer });
    setPhase('confidence');
    renderConfidence();
  } catch (error) {
    button.disabled = false;
    showError(error.message);
  }
}

function renderConfidence() {
  const task = state.task;
  const value = state.confidence == null ? 50 : state.confidence;
  document.getElementById('screen').innerHTML = `
    <section class="card">
      ${taskHeader()}
      <h2>How confident are you in your answer?</h2>
      <p class="muted">Rate your confidence in the answer you just submitted, before seeing the recommendation.</p>
      <div class="answer-summary">Your answer: ${esc(summarizeAnswer(task, state.initialAnswer))}</div>
      <div class="confidence-control">
        <div class="confidence-value"><span id="conf-val">${value}</span><span> / 100</span></div>
        <input type="range" id="confidence" min="0" max="100" step="1" value="${value}">
        <div class="scale-labels"><span>Not at all confident</span><span>Extremely confident</span></div>
      </div>
      <div class="actions">
        <button id="submit-confidence">Show recommendation</button>
      </div>
      <div id="error" class="error"></div>
    </section>`;

  const slider = document.getElementById('confidence');
  const output = document.getElementById('conf-val');
  slider.addEventListener('input', () => {
    output.textContent = slider.value;
    state.confidence = Number(slider.value);
  });
  document.getElementById('submit-confidence').addEventListener('click', submitConfidence);
}

async function submitConfidence() {
  const button = document.getElementById('submit-confidence');
  button.disabled = true;
  const confidence = Number(document.getElementById('confidence').value);
  try {
    const result = await api(
      `/api/session/${state.session.session_id}/trial/${state.trialIndex}/confidence`,
      {
        method: 'POST',
        body: JSON.stringify({ confidence }),
      },
    );
    state.confidence = confidence;
    state.recommendation = result.recommendation;
    state.evidenceAvailable = result.evidence_available;
    state.evidence = result.evidence || [];
    logEvent('confidence_submitted', { confidence });
    setPhase('recommendation');
    renderRecommendation();
  } catch (error) {
    button.disabled = false;
    showError(error.message);
  }
}

function renderRecommendation() {
  const task = state.task;
  const recommendation = state.recommendation || { text: '', structured: null };
  document.getElementById('screen').innerHTML = `
    <section class="card">
      ${taskHeader()}
      <h2>Recommendation</h2>
      <div class="recommendation-card">
        <div class="rec-label">AI recommendation</div>
        <p>${esc(recommendation.text)}</p>
        <div class="rec-answer">Recommended answer: <strong>${esc(
          summarizeAnswer(task, recommendation.structured),
        )}</strong></div>
      </div>
      <div class="verification">
        <h3>Verification</h3>
        <div id="evidence-slot"></div>
      </div>
      <div class="actions">
        <button id="to-final">Continue to final answer</button>
      </div>
      <div id="error" class="error"></div>
    </section>`;

  renderEvidenceInto(document.getElementById('evidence-slot'));
  document.getElementById('to-final').addEventListener('click', () => {
    setPhase('final');
    renderFinal();
  });
}

function evidenceTableHtml(table) {
  if (!table || !Array.isArray(table.columns) || !Array.isArray(table.rows)) return '';
  const head = table.columns.map((column) => `<th>${esc(column)}</th>`).join('');
  const body = table.rows
    .map(
      (row) =>
        `<tr>${row.map((cell) => `<td>${esc(cell)}</td>`).join('')}</tr>`,
    )
    .join('');
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function evidenceItemHtml(item) {
  return `
    <article class="evidence-item">
      <h4>${esc(item.title)}</h4>
      <pre>${esc(item.body)}</pre>
      ${evidenceTableHtml(item.table)}
    </article>`;
}

function renderEvidenceInto(slot) {
  if (!slot) return;

  if (!state.evidenceAvailable) {
    slot.innerHTML = `
      <div class="evidence-unavailable">
        <span>No verification is available for this trial. Continue with your own judgment.</span>
      </div>`;
    return;
  }

  if (!state.panelOpen) {
    slot.innerHTML = `
      <p class="small muted">Verification artifacts are available for this trial.</p>
      <button class="ghost" id="open-evidence">Show verification evidence</button>`;
    document.getElementById('open-evidence').addEventListener('click', () => {
      state.panelOpen = true;
      logEvent('panel_opened');
      renderEvidenceInto(slot);
    });
    return;
  }

  slot.innerHTML = `
    <div class="actions" style="margin-top:0">
      <button class="secondary" id="close-evidence">Hide verification evidence</button>
    </div>
    <div class="evidence-list" id="evidence-list">
      ${state.evidence.map(evidenceItemHtml).join('')}
    </div>`;

  document.getElementById('close-evidence').addEventListener('click', () => {
    state.panelOpen = false;
    logEvent('panel_closed');
    renderEvidenceInto(slot);
  });

  const list = document.getElementById('evidence-list');
  if (list) {
    list.addEventListener('scroll', () => {
      const now = performance.now();
      if (now - state.lastScrollLog > 500) {
        state.lastScrollLog = now;
        state.interactionCount += 1;
        logEvent('panel_interaction', { kind: 'scroll' });
      }
    });
    list.addEventListener('click', () => {
      state.interactionCount += 1;
      logEvent('panel_interaction', { kind: 'click' });
    });
  }
}

function renderFinal() {
  const task = state.task;
  const recommendation = state.recommendation || { text: '', structured: null };
  document.getElementById('screen').innerHTML = `
    <section class="card">
      ${taskHeader()}
      <h2>Final answer</h2>
      <p class="muted">You may keep or revise your answer. The recommendation and any available verification are shown below.</p>
      <div class="answer-summary">
        Recommendation: ${esc(summarizeAnswer(task, recommendation.structured))}
        <span class="small muted"> — ${esc(recommendation.text)}</span>
      </div>
      <details class="task-details" open>
        <summary>Review the task</summary>
        <p class="prompt">${esc(task.prompt)}</p>
        ${task.type === 'select_impl' ? '' : codeBlock(task.code)}
      </details>
      <div id="answer-area">${answerWidgetHtml(task, state.initialAnswer)}</div>
      <div class="verification">
        <h3>Verification</h3>
        <div id="evidence-slot"></div>
      </div>
      <div class="actions">
        <button id="submit-final">Submit final answer</button>
      </div>
      <div id="error" class="error"></div>
    </section>`;

  attachAnswerWidget(task, state.initialAnswer);
  renderEvidenceInto(document.getElementById('evidence-slot'));
  document.getElementById('submit-final').addEventListener('click', submitFinal);
}

async function submitFinal() {
  const button = document.getElementById('submit-final');
  button.disabled = true;
  try {
    const answer = collectAnswer(state.task);
    tick();
    if (state.inactiveSince) {
      state.maxBlurMs = Math.max(state.maxBlurMs, performance.now() - state.inactiveSince);
    }
    const payload = {
      answer,
      evidence_active_ms: Math.round(state.evidenceActiveMs),
      focus_lost_ms: Math.round(state.focusLostMs),
      max_blur_ms: Math.round(state.maxBlurMs),
      interaction_count: state.interactionCount,
    };
    const result = await api(
      `/api/session/${state.session.session_id}/trial/${state.trialIndex}/final`,
      { method: 'POST', body: JSON.stringify(payload) },
    );
    logEvent('final_submitted', {
      answer,
      evidence_active_ms: payload.evidence_active_ms,
      focus_lost_ms: payload.focus_lost_ms,
      max_blur_ms: payload.max_blur_ms,
      interaction_count: payload.interaction_count,
    });
    updateProgress(state.trialIndex + 1);
    if (result.session_complete) {
      setPhase('complete');
      renderCompletion();
    } else if (result.block_complete) {
      setPhase('break');
      renderBreak(result.next_trial_index);
    } else {
      await loadTrial(result.next_trial_index);
    }
  } catch (error) {
    button.disabled = false;
    showError(error.message);
  }
}

function renderAlreadySubmitted(data) {
  setPhase('recorded');
  document.getElementById('screen').innerHTML = `
    <section class="card">
      ${taskHeader()}
      <h2>Trial already recorded</h2>
      <p class="muted">This trial's final answer was already submitted. Continue with the session.</p>
      <div class="actions"><button id="continue">Continue</button></div>
    </section>`;
  document.getElementById('continue').addEventListener('click', () => {
    if (data.next_trial_index == null) {
      renderCompletion();
    } else {
      loadTrial(data.next_trial_index);
    }
  });
}

function renderBreak(nextIndex) {
  const completed = state.trialIndex + 1;
  document.getElementById('screen').innerHTML = `
    <section class="card break">
      <div class="big">✓</div>
      <h2>Block complete</h2>
      <p class="muted">You have completed ${completed} of ${state.session.total_trials} tasks. Take a short break, then continue with the next block.</p>
      <div class="actions" style="justify-content:center">
        <button id="continue">Continue</button>
      </div>
    </section>`;
  document.getElementById('continue').addEventListener('click', () => loadTrial(nextIndex));
}

// ---------------------------------------------------------------------------
// Completion
// ---------------------------------------------------------------------------

function renderCompletion() {
  setPhase('complete');
  updateProgress(state.session.total_trials);
  const dryRun = state.session.mode === 'dry_run';
  document.getElementById('screen').innerHTML = `
    <section class="card">
      <h2>${dryRun ? 'Dry run complete' : 'Session complete'}</h2>
      <p class="muted">
        ${dryRun
          ? 'Thank you for testing the interface. Please record what broke or what was confusing. This is not research data.'
          : 'Thank you for completing the pilot session. Please answer the short questions below.'}
      </p>
      <label for="clarity">How clear were the instructions and screens?</label>
      <select id="clarity">
        <option value="">Select…</option>
        <option value="5">5 — very clear</option>
        <option value="4">4 — clear</option>
        <option value="3">3 — neutral</option>
        <option value="2">2 — confusing</option>
        <option value="1">1 — very confusing</option>
      </select>
      <label for="issues">${dryRun ? 'What broke or behaved unexpectedly?' : 'Did anything in the interface behave unexpectedly?'}</label>
      <textarea id="issues" placeholder="Optional"></textarea>
      <label for="comments">${dryRun ? 'What should be fixed before the pilot?' : 'Any other comments?'}</label>
      <textarea id="comments" placeholder="Optional"></textarea>
      <div class="actions">
        <button id="finish">${dryRun ? 'Send feedback' : 'Finish session'}</button>
      </div>
      <div id="error" class="error"></div>
    </section>`;

  document.getElementById('finish').addEventListener('click', async () => {
    const button = document.getElementById('finish');
    button.disabled = true;
    const questionnaire = {
      clarity: document.getElementById('clarity').value || null,
      issues: document.getElementById('issues').value.trim(),
      comments: document.getElementById('comments').value.trim(),
      mode: state.session.mode,
    };
    try {
      await api(`/api/session/${state.session.session_id}/complete`, {
        method: 'POST',
        body: JSON.stringify({ questionnaire }),
      });
      localStorage.removeItem('pilot_session_id');
      document.getElementById('screen').innerHTML = `
        <section class="card break">
          <div class="big">✓</div>
          <h2>${dryRun ? 'Feedback recorded' : 'Thank you'}</h2>
          <p class="muted">${dryRun ? 'The interface test is finished.' : 'Your session has been recorded. You may close this tab.'}</p>
          <p class="small muted">Session: ${esc(state.session.session_id)}</p>
        </section>`;
    } catch (error) {
      button.disabled = false;
      showError(error.message);
    }
  });
}
