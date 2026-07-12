(function () {
  const body = document.getElementById("body");
  const eyebrow = document.getElementById("eyebrow");
  const phaseTitle = document.getElementById("phase-title");
  const timerBlock = document.getElementById("timer-block");
  const timerEl = document.getElementById("timer");
  const timerLabel = document.getElementById("timer-label");
  const objectiveBlock = document.getElementById("objective-block");
  const hostBlock = document.getElementById("host-block");
  const mainBlock = document.getElementById("main-block");
  const playersBlock = document.getElementById("players-block");

  let ws;
  let currentBallot = {}; // target_id -> {snake, honesty}, kept while on vote screen

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : s;
    return d.innerHTML;
  }

  function connect() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}/ws`);
    ws.onmessage = (evt) => render(JSON.parse(evt.data));
    ws.onclose = () => setTimeout(connect, 1500);
  }

  function send(payload) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(payload));
  }

  function render(state) {
    body.className = "phase-" + state.phase;
    eyebrow.textContent = state.phase === "lobby" ? "Waiting to start" : `Round ${state.round_number}`;

    const titles = {
      lobby: "The table is filling up",
      action: "Spread or investigate",
      vote: "Cast your ballot",
      gameover: "The whole story",
    };
    phaseTitle.textContent = titles[state.phase] || state.phase;

    if (state.time_remaining !== null && (state.phase === "action" || state.phase === "vote")) {
      timerBlock.style.display = "";
      const m = Math.floor(state.time_remaining / 60);
      const s = String(state.time_remaining % 60).padStart(2, "0");
      timerEl.textContent = `${m}:${s}`;
      timerLabel.textContent = state.phase === "action" ? "until the floor closes" : "until votes are tallied";
    } else {
      timerBlock.style.display = "none";
    }

    renderObjective(state);
    renderHost(state);

    if (state.phase === "lobby") renderLobby(state);
    else if (state.phase === "action") renderAction(state);
    else if (state.phase === "vote") renderVote(state);
    else if (state.phase === "gameover") renderGameOver(state);

    renderPlayers(state);
  }

  function renderObjective(state) {
    if (!state.my_objective || state.phase === "lobby" || state.phase === "gameover") {
      objectiveBlock.innerHTML = "";
      return;
    }
    objectiveBlock.innerHTML = `
      <div class="objective-box">
        <div class="eyebrow">Your secret objective</div>
        <div>${esc(state.my_objective)}</div>
      </div>`;
  }

  function renderHost(state) {
    if (!state.you_are_host) { hostBlock.innerHTML = ""; return; }

    if (state.phase === "lobby") {
      const enough = state.players.length >= 2;
      hostBlock.innerHTML = `
        <div class="card host-panel">
          <div class="eyebrow">Host controls</div>
          <p>${state.players.length} player${state.players.length === 1 ? "" : "s"} at the table.
             ${enough ? "Ready when you are." : "Need at least 2 to start."}</p>
          <button id="btn-start" ${enough ? "" : "disabled"}>Start the game</button>
        </div>`;
      document.getElementById("btn-start").onclick = () => send({ type: "host_start" });
    } else if (state.phase === "action" || state.phase === "vote") {
      hostBlock.innerHTML = `
        <div class="card host-panel">
          <div class="eyebrow">Host controls</div>
          <div class="host-actions">
            <button class="secondary" id="btn-end-round">End round early</button>
            <button class="danger" id="btn-end-game">End the game</button>
          </div>
        </div>`;
      document.getElementById("btn-end-round").onclick = () => send({ type: "host_end_round" });
      document.getElementById("btn-end-game").onclick = () => {
        if (confirm("End the game and reveal everyone's secret objectives?")) send({ type: "host_end_game" });
      };
    } else if (state.phase === "gameover") {
      hostBlock.innerHTML = `
        <div class="card host-panel">
          <div class="eyebrow">Host controls</div>
          <button id="btn-reset">Reset lobby &amp; start a new game</button>
        </div>`;
      document.getElementById("btn-reset").onclick = () => {
        if (confirm("This wipes the current game for everyone. Continue?")) send({ type: "host_reset" });
      };
    }
  }

  function renderLobby(state) {
    mainBlock.innerHTML = `<div class="card"><p style="margin:0;color:var(--text-dim);">
      Waiting for the host to start the game&hellip; everyone's rumors and secret objectives get dealt out the moment it begins.
    </p></div>`;
  }

  function renderAction(state) {
    if (state.i_have_acted) {
      mainBlock.innerHTML = `<div class="card glow"><p style="margin:0;">
        You've made your move this round. <span class="status-pill acted">Locked in</span><br>
        <span style="color:var(--text-dim);font-size:0.85rem;">Waiting on everyone else&hellip;</span>
      </p></div>`;
      return;
    }

    if (state.rumors.length === 0) {
      mainBlock.innerHTML = `<div class="empty-note">No rumors currently in play.</div>`;
      return;
    }

    mainBlock.innerHTML = state.rumors.map(r => `
      <div class="rumor">
        <div class="rumor-text">${esc(r.text)}</div>
        <div class="rumor-meta">
          <span class="severity ${r.severity}">${r.severity}</span>
          <span>Popularity ${r.popularity}</span>
        </div>
        <div class="rumor-actions">
          <button class="secondary" data-rid="${r.id}" data-act="spread">Spread it</button>
          <button class="secondary" data-rid="${r.id}" data-act="investigate">Investigate</button>
        </div>
      </div>
    `).join("");

    mainBlock.querySelectorAll("button[data-act]").forEach(btn => {
      btn.onclick = () => {
        send({ type: "action", action: btn.dataset.act, rumor_id: btn.dataset.rid });
      };
    });
  }

  function renderVote(state) {
    if (state.i_have_voted) {
      mainBlock.innerHTML = `<div class="card glow"><p style="margin:0;">
        Ballot cast. <span class="status-pill acted">Locked in</span><br>
        <span style="color:var(--text-dim);font-size:0.85rem;">Waiting on everyone else&hellip;</span>
      </p></div>`;
      return;
    }

    const others = state.players.filter(p => !p.is_you);
    if (others.length === 0) {
      mainBlock.innerHTML = `<div class="empty-note">Nobody else to vote on.</div>`;
      return;
    }

    currentBallot = {};
    others.forEach(p => { currentBallot[p.id] = { snake: 0, honesty: 0 }; });

    mainBlock.innerHTML = `
      <div class="card">
        <p style="margin-top:0;color:var(--text-dim);font-size:0.85rem;">
          Rate everyone else: how much of a Snake were they this round, and how much did they help uncover the truth?
        </p>
        ${others.map(p => `
          <div class="vote-row">
            <div class="player-name">${esc(p.name)}</div>
            <div class="vote-sliders">
              <div class="vote-slider">
                <label style="margin:6px 0 2px;">Snake <span class="value" id="snake-val-${p.id}">0</span></label>
                <input type="range" min="0" max="3" value="0" data-pid="${p.id}" data-cat="snake" style="width:100%;">
              </div>
              <div class="vote-slider">
                <label style="margin:6px 0 2px;">Honesty <span class="value" id="honesty-val-${p.id}">0</span></label>
                <input type="range" min="0" max="3" value="0" data-pid="${p.id}" data-cat="honesty" style="width:100%;">
              </div>
            </div>
          </div>
        `).join("")}
        <button id="btn-cast-vote">Cast ballot</button>
      </div>
    `;

    mainBlock.querySelectorAll("input[type=range]").forEach(inp => {
      inp.oninput = () => {
        const pid = inp.dataset.pid, cat = inp.dataset.cat;
        currentBallot[pid][cat] = parseInt(inp.value, 10);
        document.getElementById(`${cat}-val-${pid}`).textContent = inp.value;
      };
    });

    document.getElementById("btn-cast-vote").onclick = () => {
      send({ type: "vote", ballot: currentBallot });
    };
  }

  function renderGameOver(state) {
    if (!state.final_results) { mainBlock.innerHTML = ""; return; }
    mainBlock.innerHTML = `
      <div class="card">
        <div class="eyebrow">Final standings, by Reputation</div>
        ${state.final_results.map((r, i) => `
          <div class="result-row">
            <div style="display:flex;gap:10px;">
              <div class="result-rank">${i + 1}</div>
              <div>
                <div class="player-name">${esc(r.name)}</div>
                ${r.objective_text ? `<div class="result-obj ${r.objective_completed ? "completed" : ""}">
                  ${r.objective_completed ? "&#10003; Completed" : "&#10007; Missed"} &mdash; ${esc(r.objective_text)}
                </div>` : ""}
              </div>
            </div>
            <div class="stat-grid" style="grid-template-columns:repeat(3,1fr);">
              <div><strong>${r.reputation}</strong>Rep</div>
              <div><strong>${r.snake_score}</strong>Snake</div>
              <div><strong>${r.honesty_score}</strong>Honesty</div>
            </div>
          </div>
        `).join("")}
      </div>`;
  }

  function renderPlayers(state) {
    if (state.phase === "gameover") { playersBlock.innerHTML = ""; return; }
    playersBlock.innerHTML = `
      <div class="card">
        <div class="eyebrow">At the table</div>
        ${state.players.map(p => `
          <div class="player-row">
            ${p.photo ? `<img class="avatar" src="/static/uploads/${p.photo}">` : `<div class="avatar"></div>`}
            <div style="flex:1;">
              <div class="player-name">${esc(p.name)}${p.is_you ? " (you)" : ""}${p.is_host ? " &#9679; host" : ""}</div>
              <div class="player-tag">${esc(p.descriptor || "")}</div>
            </div>
            <div class="stat-grid">
              <div><strong>${p.reputation}</strong>Rep</div>
              <div><strong>${p.influence}</strong>Inf</div>
            </div>
          </div>
        `).join("")}
      </div>`;
  }

  connect();
})();
