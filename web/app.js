/* Touhou 1cc Tracker frontend. Talks to Python through window.pywebview.api. */

var state = {
  games: [],
  currentGameId: null,
  currentGame: null,   // full game row from get_grid (exe_path, playtime)
  highlight: null,     // {shotTypeId, difficulty} to flash after a picker jump
  playing: {},         // gameId -> true while a launched session runs
  stopwatches: {}      // gameId -> Date.now() at stopwatch start
};

var STATUS_LABEL = {
  not_cleared: "·", cleared: "C", one_cc: "★",
  one_cc_no_bomb: "NB", one_cc_no_miss: "NM", one_cc_nmnb: "NMNB"
};
var STATUS_NAME = {
  not_cleared: "not cleared", cleared: "cleared", one_cc: "1cc",
  one_cc_no_bomb: "1cc, no bombs", one_cc_no_miss: "1cc, no misses",
  one_cc_nmnb: "NMNB — perfect run"
};

function api() { return window.pywebview.api; }
function el(id) { return document.getElementById(id); }

function setStatus(msg) { el("statusbar").textContent = msg; }

function esc(s) {
  var d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

/* ---------- init ---------- */

window.addEventListener("pywebviewready", function () {
  api().get_games().then(function (games) {
    state.games = games;
    renderGameList();
    selectGame(games[0].id);
  });
});

function renderGameList() {
  var ul = el("game-list");
  ul.innerHTML = "";
  state.games.forEach(function (g) {
    var li = document.createElement("li");
    var a = document.createElement("a");
    a.href = "#";
    a.id = "game-link-" + g.id;
    a.innerHTML = '<span class="th-num">TH' +
      String(g.number).padStart(2, "0") + "</span> " + esc(g.title);
    a.onclick = function (e) { e.preventDefault(); selectGame(g.id); };
    li.appendChild(a);
    ul.appendChild(li);
  });
}

/* ---------- grid view ---------- */

function selectGame(gameId) {
  state.currentGameId = gameId;
  var links = el("game-list").getElementsByTagName("a");
  for (var i = 0; i < links.length; i++) {
    links[i].className = links[i].id === "game-link-" + gameId ? "active" : "";
  }
  showView("grid");
  api().get_grid(gameId).then(renderGrid);
}

function renderGrid(data) {
  state.currentGame = data.game;
  renderToolbar();
  el("grid-title").innerHTML = "▪ TH" +
    String(data.game.number).padStart(2, "0") + " " + esc(data.game.title) +
    " (" + data.game.year + ") ▪";

  var html = '<table class="grid"><tr><th class="shot-col">Shot Type</th>';
  data.columns.forEach(function (c) { html += "<th>" + c + "</th>"; });
  html += "</tr>";

  data.shots.forEach(function (shot) {
    html += '<tr><td class="shot-name">' + esc(shot.name) + "</td>";
    data.columns.forEach(function (diff) {
      var cell = shot.cells[diff];
      if (!cell) {
        html += '<td class="ineligible">&mdash;</td>';
      } else {
        var tip = STATUS_NAME[cell.status] + (cell.date ? " (" + cell.date + ")" : "");
        html += '<td class="cell st-' + cell.status + '"' +
          ' id="cell-' + shot.id + "-" + diff + '"' +
          ' title="' + esc(shot.name) + " / " + diff + ": " + tip + '"' +
          " onclick=\"cycleCell(" + shot.id + ",'" + diff + "')\">" +
          STATUS_LABEL[cell.status] + "</td>";
      }
    });
    html += "</tr>";
  });
  html += "</table>";
  el("grid-container").innerHTML = html;

  if (state.highlight) {
    var target = el("cell-" + state.highlight.shotTypeId + "-" + state.highlight.difficulty);
    if (target) {
      target.classList.add("highlight");
      target.scrollIntoView({ block: "center" });
    }
    state.highlight = null;
  }
}

function cycleCell(shotTypeId, difficulty) {
  api().cycle_status(shotTypeId, difficulty).then(function (res) {
    var cell = el("cell-" + shotTypeId + "-" + difficulty);
    cell.className = "cell st-" + res.status;
    cell.textContent = STATUS_LABEL[res.status];
    var tip = STATUS_NAME[res.status] + (res.date ? " (" + res.date + ")" : "");
    cell.title = difficulty + ": " + tip;
    setStatus(difficulty + " set to " + STATUS_NAME[res.status] +
      (res.status === "one_cc" ? " ★ Congratulations!" : ""));
  });
}

/* ---------- session toolbar (v2) ---------- */

function fmtMinutes(m) {
  var h = Math.floor(m / 60);
  return (h ? h + "h " : "") + (m % 60) + "m";
}

function renderToolbar() {
  var g = state.currentGame;
  if (!g) return;
  el("playtime-total").textContent = "Playtime: " + fmtMinutes(g.playtime_minutes);
  var exe = g.exe_path ? g.exe_path.split(/[\\\/]/).pop() : "no exe set";
  el("exe-info").innerHTML = esc(exe) +
    ' [<a href="#" id="set-exe">change</a>]';
  el("set-exe").onclick = function (e) {
    e.preventDefault();
    chooseExe(state.currentGameId, null);
  };
  updatePlayButton();
  updateStopwatchButton();
}

function chooseExe(gameId, andThen) {
  setStatus("Choose the game executable (vpatch/thcrap loaders work too)…");
  api().set_executable(gameId).then(function (res) {
    if (res.cancelled) { setStatus("Ready."); return; }
    if (state.currentGame && state.currentGameId === gameId) {
      state.currentGame.exe_path = res.exe_path;
      renderToolbar();
    }
    setStatus("Executable set.");
    if (andThen) andThen();
  });
}

function updatePlayButton() {
  var btn = el("btn-play");
  if (state.playing[state.currentGameId]) {
    btn.disabled = true;
    btn.textContent = "▶ Playing…";
  } else {
    btn.disabled = false;
    btn.textContent = "▶ Play";
  }
}

function updateStopwatchButton() {
  var btn = el("btn-stopwatch");
  var start = state.stopwatches[state.currentGameId];
  if (start) {
    var s = Math.floor((Date.now() - start) / 1000);
    btn.textContent = "⏹ Stop " + Math.floor(s / 60) + ":" +
      String(s % 60).padStart(2, "0");
    btn.className = "running";
  } else {
    btn.textContent = "⏱ Stopwatch";
    btn.className = "";
  }
}
setInterval(function () {
  if (state.stopwatches[state.currentGameId]) updateStopwatchButton();
}, 1000);

function refreshCurrentView() {
  if (el("view-dashboard").style.display !== "none") {
    api().get_dashboard().then(renderDashboard);
  } else if (state.currentGameId) {
    api().get_grid(state.currentGameId).then(renderGrid);
  }
}

el("btn-play").onclick = function () {
  var gid = state.currentGameId;
  api().play(gid).then(function (res) {
    if (res.needs_exe) {
      if (confirm("No executable is set for this game yet.\nChoose it now?")) {
        chooseExe(gid, function () { el("btn-play").onclick(); });
      }
    } else if (res.already_running) {
      setStatus("A session for this game is already being timed.");
    } else if (res.error) {
      setStatus(res.error);
    } else {
      state.playing[gid] = true;
      updatePlayButton();
      setStatus("Game launched — session is being timed. Just play!");
    }
  });
};

el("btn-stopwatch").onclick = function () {
  var gid = state.currentGameId;
  if (state.stopwatches[gid]) {
    api().stopwatch_stop(gid).then(function (res) {
      delete state.stopwatches[gid];
      updateStopwatchButton();
      if (res.error) setStatus(res.error);
      else if (res.stored) {
        setStatus("Stopwatch session saved: " + fmtMinutes(res.minutes));
        refreshCurrentView();
      } else setStatus("Stopwatch under 1 minute — discarded.");
    });
  } else {
    api().stopwatch_start(gid).then(function () {
      state.stopwatches[gid] = Date.now();
      updateStopwatchButton();
      setStatus("Stopwatch running…");
    });
  }
};

el("btn-log").onclick = function () {
  var form = el("log-form");
  var show = form.style.display !== "inline";
  form.style.display = show ? "inline" : "none";
  if (show && !el("log-date").value) {
    el("log-date").value = new Date().toISOString().slice(0, 10);
  }
};

el("log-save").onclick = function () {
  api().add_manual_session(
    state.currentGameId, el("log-date").value, el("log-minutes").value
  ).then(function (res) {
    if (res.error) { setStatus(res.error); return; }
    setStatus("Logged " + fmtMinutes(res.minutes) + " — nice work.");
    el("log-form").style.display = "none";
    el("log-minutes").value = "";
    refreshCurrentView();
  });
};

/* Called from Python via evaluate_js when a launched session finishes. */
function sessionEnded(gameId, minutes) {
  delete state.playing[gameId];
  updatePlayButton();
  setStatus(minutes >= 1
    ? "Session saved: " + fmtMinutes(minutes)
    : "Session under 1 minute — discarded (misclick rule).");
  refreshCurrentView();
}

function sessionFailed(gameId, message) {
  delete state.playing[gameId];
  updatePlayButton();
  setStatus("Could not launch game: " + message);
}

/* ---------- dashboard view ---------- */

function pct(part, total) {
  return total ? (100 * part / total).toFixed(1) + "%" : "-";
}

function bar(part, total) {
  var w = total ? Math.round(140 * part / total) : 0;
  return '<span class="bar-track"><span class="bar-fill" style="width:' +
    w + 'px;display:block"></span></span>';
}

var TIER_KEYS = ["one_cc", "one_cc_no_bomb", "one_cc_no_miss", "one_cc_nmnb"];

function dashTable(rows, labelHeader, labelOf, withPlaytime) {
  var html = '<table class="dash"><tr><th>' + labelHeader +
    "</th><th>1cc</th><th>NB</th><th>NM</th><th>NMNB</th>" +
    "<th>Cleared</th><th>Remaining</th><th>Total</th>" +
    "<th>1cc %</th><th>Progress</th>" +
    (withPlaytime ? "<th>Playtime</th>" : "") + "</tr>";
  var t = { total: 0, cleared: 0, one_cc_plus: 0, minutes: 0 };
  TIER_KEYS.forEach(function (k) { t[k] = 0; });

  function row(r, label, cls) {
    var cells = "<tr" + (cls ? ' class="' + cls + '"' : "") + "><td>" + label + "</td>";
    TIER_KEYS.forEach(function (k) {
      cells += '<td class="num">' + r[k] + "</td>";
    });
    cells += '<td class="num">' + r.cleared + "</td>" +
      '<td class="num">' + (r.total - r.one_cc_plus) + "</td>" +
      '<td class="num">' + r.total + "</td>" +
      '<td class="num">' + pct(r.one_cc_plus, r.total) + "</td>" +
      "<td>" + bar(r.one_cc_plus, r.total) + "</td>" +
      (withPlaytime ? '<td class="num">' + fmtMinutes(r.minutes || 0) + "</td>" : "") +
      "</tr>";
    return cells;
  }

  rows.forEach(function (r) {
    t.total += r.total; t.cleared += r.cleared; t.one_cc_plus += r.one_cc_plus;
    t.minutes += r.minutes || 0;
    TIER_KEYS.forEach(function (k) { t[k] += r[k]; });
    html += row(r, labelOf(r));
  });
  html += row(t, "TOTAL", "total-row") + "</table>";
  return html;
}

function renderDashboard(data) {
  el("dashboard-container").innerHTML =
    '<div class="dash-section">By game</div>' +
    dashTable(data.games, "Game", function (g) {
      return "TH" + String(g.number).padStart(2, "0") + " " + esc(g.title);
    }, true) +
    '<div class="dash-section">By difficulty</div>' +
    dashTable(data.difficulties, "Difficulty", function (d) {
      return esc(d.difficulty);
    }, false);
}

/* ---------- what-next picker ---------- */

el("pick-button").onclick = function () {
  var diff = el("pick-difficulty").value || null;
  api().pick_next(diff).then(function (pick) {
    var box = el("pick-result");
    box.style.display = "block";
    if (!pick) {
      box.innerHTML = "Nothing left — you have 1cc'd everything?!";
      return;
    }
    box.innerHTML = "Go for: <b>" + esc(pick.shot_name) + "</b><br>" +
      pick.difficulty + " · TH" + String(pick.game_number).padStart(2, "0") +
      " " + esc(pick.game_title) + "<br>" +
      '<a href="#" id="pick-jump">&raquo; jump to cell</a>';
    el("pick-jump").onclick = function (e) {
      e.preventDefault();
      state.highlight = { shotTypeId: pick.shot_type_id, difficulty: pick.difficulty };
      selectGame(pick.game_id);
    };
  });
};

/* ---------- view switching ---------- */

function showView(name) {
  el("view-grid").style.display = name === "grid" ? "" : "none";
  el("view-dashboard").style.display = name === "dashboard" ? "" : "none";
}

el("nav-grid").onclick = function (e) {
  e.preventDefault();
  if (state.currentGameId) selectGame(state.currentGameId);
};
el("nav-dashboard").onclick = function (e) {
  e.preventDefault();
  showView("dashboard");
  api().get_dashboard().then(renderDashboard);
};
