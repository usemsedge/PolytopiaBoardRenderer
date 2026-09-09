(() => {
  const boardImg = document.getElementById("board");
  const hit = document.getElementById("hit");
  const statusEl = document.getElementById("status");
  const menusEl = document.getElementById("menus");
  const modLabel = document.getElementById("mod-label");
  const playerSelect = document.getElementById("player-select");
  const playerSwatch = document.getElementById("player-swatch");
  const shareInput = document.getElementById("share-input");
  const shareLoadBtn = document.getElementById("share-load");
  const shareStart = document.getElementById("share-start");
  const debugPanel = document.getElementById("debug-panel");
  const debugTitle = document.getElementById("debug-title");
  const debugBody = document.getElementById("debug-body");
  const debugClose = document.getElementById("debug-close");

  let meta = null;
  let session = null;
  let painting = false;
  let loadingShare = false;
  let selected = null;

  function setStatus(msg) {
    statusEl.textContent = msg || "";
  }

  async function api(path, opts) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(opts && opts.headers) },
      ...opts,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || res.statusText);
    return data;
  }

  function syncPlayerUI() {
    if (!session) return;
    playerSelect.innerHTML = "";
    for (const p of session.players) {
      const opt = document.createElement("option");
      opt.value = String(p.id);
      opt.textContent = `${p.user_name} · ${p.tribe_name}`;
      if (p.id === session.selected_player_id) opt.selected = true;
      playerSelect.appendChild(opt);
    }
    const cur = session.players.find((p) => p.id === session.selected_player_id);
    playerSwatch.style.background = cur ? cur.color : "#666";
  }

  function syncModUI() {
    if (!session) return;
    modLabel.textContent = session.modification_label || "None selected";
    const mod = session.modification || {};
    for (const btn of menusEl.querySelectorAll(".item, .remove-item")) {
      const cat = btn.dataset.category;
      const remove = btn.dataset.remove === "1";
      const value = btn.dataset.value !== undefined ? Number(btn.dataset.value) : null;
      let active = false;
      if (mod.category === cat) {
        if (remove && mod.remove) active = true;
        if (!remove && !mod.remove && Number(mod.value) === value) active = true;
      }
      btn.classList.toggle("active", active);
    }
  }

  function buildMenus() {
    menusEl.innerHTML = "";
    if (!session || !session.catalog) return;
    for (const menu of session.catalog.menus) {
      const wrap = document.createElement("div");
      wrap.className = "menu";
      wrap.dataset.menu = menu.id;

      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "menu-toggle";
      toggle.innerHTML = `<span>${menu.label}</span><span class="chev">▾</span>`;
      toggle.addEventListener("click", () => {
        wrap.classList.toggle("open");
      });

      const body = document.createElement("div");
      body.className = "menu-body";

      if (menu.can_remove) {
        const rem = document.createElement("button");
        rem.type = "button";
        rem.className = "remove-item";
        rem.dataset.category = menu.id;
        rem.dataset.remove = "1";
        rem.textContent = `Remove ${menu.label.toLowerCase()}`;
        rem.addEventListener("click", () => selectMod(menu.id, null, true));
        body.appendChild(rem);
      }

      for (const item of menu.items) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "item";
        btn.dataset.category = menu.id;
        btn.dataset.value = String(item.id);
        btn.dataset.remove = "0";
        const left = document.createElement("span");
        left.textContent = item.label;
        btn.appendChild(left);
        if (menu.id === "unit" && item.cost != null) {
          const cost = document.createElement("span");
          cost.className = "cost";
          cost.textContent = `${item.cost}★`;
          btn.appendChild(cost);
        }
        btn.addEventListener("click", () => selectMod(menu.id, item.id, false));
        body.appendChild(btn);
      }

      wrap.appendChild(toggle);
      wrap.appendChild(body);
      menusEl.appendChild(wrap);
    }
    syncModUI();
  }

  async function selectMod(category, value, remove) {
    try {
      session = await api("/api/modification", {
        method: "PUT",
        body: JSON.stringify({ category, value, remove }),
      });
      syncModUI();
      setStatus(session.modification_label);
    } catch (e) {
      setStatus(e.message);
    }
  }

  async function loadBoardImage() {
    const bust = `t=${Date.now()}`;
    await new Promise((resolve, reject) => {
      boardImg.onload = resolve;
      boardImg.onerror = () => reject(new Error("board image failed"));
      boardImg.src = `/api/board.jpg?${bust}`;
    });
  }

  async function refreshBoard(fullMeta = false) {
    const bust = `t=${Date.now()}`;
    if (fullMeta || !meta) {
      meta = await api(`/api/board/meta?${bust}`);
      hit.width = meta.image_w;
      hit.height = meta.image_h;
      hit.style.width = `${meta.image_w}px`;
      hit.style.height = `${meta.image_h}px`;
    }
    // Meta fetch already rendered+cached; image endpoint reuses that cache.
    await loadBoardImage();
    drawSelection();
  }

  function drawSelection() {
    const ctx = hit.getContext("2d");
    ctx.clearRect(0, 0, hit.width, hit.height);
    if (!selected || !meta) return;
    const xy = meta.tile_centers[`${selected.x},${selected.y}`];
    if (!xy) return;
    const [cx, cy] = xy;
    const hw = meta.half_w || meta.tile_size || 128;
    const hh = meta.half_h || hw * 0.6;
    ctx.beginPath();
    ctx.moveTo(cx, cy - hh);
    ctx.lineTo(cx + hw, cy);
    ctx.lineTo(cx, cy + hh);
    ctx.lineTo(cx - hw, cy);
    ctx.closePath();
    ctx.lineJoin = "round";
    ctx.strokeStyle = "rgba(32, 32, 32, 0.45)";
    ctx.lineWidth = 5;
    ctx.stroke();
    ctx.strokeStyle = "rgba(196, 196, 196, 0.95)";
    ctx.lineWidth = 2.25;
    ctx.stroke();
  }

  function hitTest(clientX, clientY) {
    if (!meta) return null;
    const rect = hit.getBoundingClientRect();
    const scaleX = hit.width / rect.width;
    const scaleY = hit.height / rect.height;
    const px = (clientX - rect.left) * scaleX;
    const py = (clientY - rect.top) * scaleY;
    const hw = meta.half_w || meta.tile_size || 128;
    const hh = meta.half_h || hw * 0.6;

    let best = null;
    let bestD = Infinity;
    for (const [key, xy] of Object.entries(meta.tile_centers)) {
      const [cx, cy] = xy;
      const dx = Math.abs(px - cx) / hw;
      const dy = Math.abs(py - cy) / hh;
      if (dx + dy <= 1.05) {
        const d = dx + dy;
        if (d < bestD) {
          bestD = d;
          const [x, y] = key.split(",").map(Number);
          best = { x, y };
        }
      }
    }
    return best;
  }

  function showDebug(payload) {
    debugPanel.hidden = false;
    debugTitle.textContent = `Tile (${payload.x}, ${payload.y})`;
    const parts = [
      "— tile —",
      JSON.stringify(payload.tile, null, 2),
      "",
      "— unit —",
      payload.unit == null ? "null" : JSON.stringify(payload.unit, null, 2),
    ];
    debugBody.textContent = parts.join("\n");
  }

  async function inspectAt(x, y) {
    const payload = await api(`/api/tile?x=${x}&y=${y}`);
    showDebug(payload);
  }

  async function onBoardClick(clientX, clientY) {
    const tile = hitTest(clientX, clientY);
    if (!tile) {
      setStatus("No tile under cursor");
      return;
    }
    selected = { x: tile.x, y: tile.y };
    drawSelection();
    try {
      await inspectAt(tile.x, tile.y);
    } catch (e) {
      setStatus(e.message);
      return;
    }
    const hasBrush = session && session.modification && session.modification.category;
    if (!hasBrush) {
      setStatus(`Inspect (${tile.x}, ${tile.y})`);
      return;
    }
    if (painting) return;
    painting = true;
    try {
      await api("/api/paint", {
        method: "POST",
        body: JSON.stringify({ x: tile.x, y: tile.y }),
      });
      await refreshBoard(false);
      await inspectAt(tile.x, tile.y);
      setStatus(`Applied at (${tile.x}, ${tile.y}) · ${session.modification_label}`);
    } catch (e) {
      setStatus(e.message);
    } finally {
      painting = false;
    }
  }

  hit.addEventListener("click", (ev) => {
    onBoardClick(ev.clientX, ev.clientY);
  });

  debugClose.addEventListener("click", () => {
    debugPanel.hidden = true;
  });

  hit.addEventListener("mousemove", (ev) => {
    const tile = hitTest(ev.clientX, ev.clientY);
    if (tile) setStatus(`Tile (${tile.x}, ${tile.y})`);
  });

  playerSelect.addEventListener("change", async () => {
    try {
      session = await api("/api/player", {
        method: "PUT",
        body: JSON.stringify({ player_id: Number(playerSelect.value) }),
      });
      syncPlayerUI();
      // Perspective change updates fog + unit action chrome.
      await refreshBoard(true);
      setStatus(`Player ${session.selected_player_id}`);
    } catch (e) {
      setStatus(e.message);
    }
  });

  async function applySession(next) {
    session = next;
    syncPlayerUI();
    buildMenus();
    syncModUI();
    selected = null;
    meta = null;
    await refreshBoard(true);
  }

  async function loadShareLink() {
    const link = (shareInput.value || "").trim();
    if (!link) {
      setStatus("Paste a Polytopia share link first");
      return;
    }
    if (loadingShare) return;
    loadingShare = true;
    shareLoadBtn.disabled = true;
    setStatus("Fetching share link…");
    try {
      const which = shareStart.checked ? "start" : "end";
      const next = await api("/api/load_share", {
        method: "POST",
        body: JSON.stringify({
          share_link: link,
          allow_unfinished: true,
          which,
        }),
      });
      await applySession(next);
      const info = next.loaded || {};
      const turn = info.current_turn != null ? info.current_turn : next.current_turn;
      const size =
        info.map_width != null
          ? `${info.map_width}×${info.map_height}`
          : `${next.map_width}×${next.map_height}`;
      const snap = (info.which || which) === "start" ? "game start" : "game end";
      setStatus(
        `Loaded ${info.game_id || "game"} · ${snap} · turn ${turn ?? "?"} · ${size}` +
          (info.from_cache ? " · cached" : "")
      );
      if (info.share_link) shareInput.value = info.share_link;
    } catch (e) {
      setStatus(e.message || String(e));
    } finally {
      loadingShare = false;
      shareLoadBtn.disabled = false;
    }
  }

  shareLoadBtn.addEventListener("click", () => {
    loadShareLink();
  });

  shareInput.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") {
      ev.preventDefault();
      loadShareLink();
    }
  });

  async function boot() {
    setStatus("Loading…");
    session = await api("/api/session");
    syncPlayerUI();
    buildMenus();
    syncModUI();
    await refreshBoard(true);
    setStatus("Ready");
  }

  boot().catch((e) => setStatus(e.message || String(e)));
})();
