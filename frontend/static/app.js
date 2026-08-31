(() => {
  const boardImg = document.getElementById("board");
  const hit = document.getElementById("hit");
  const statusEl = document.getElementById("status");
  const menusEl = document.getElementById("menus");
  const modLabel = document.getElementById("mod-label");
  const playerSelect = document.getElementById("player-select");
  const playerSwatch = document.getElementById("player-swatch");

  let meta = null;
  let session = null;
  let painting = false;

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

  async function paintAt(clientX, clientY) {
    if (!session || !session.modification || !session.modification.category) {
      setStatus("Select a modification first");
      return;
    }
    const tile = hitTest(clientX, clientY);
    if (!tile) {
      setStatus("No tile under cursor");
      return;
    }
    if (painting) return;
    painting = true;
    try {
      await api("/api/paint", {
        method: "POST",
        body: JSON.stringify({ x: tile.x, y: tile.y }),
      });
      // Tile centers are stable; only re-fetch the composited image.
      await refreshBoard(false);
      setStatus(`Applied at (${tile.x}, ${tile.y}) · ${session.modification_label}`);
    } catch (e) {
      setStatus(e.message);
    } finally {
      painting = false;
    }
  }

  hit.addEventListener("click", (ev) => {
    paintAt(ev.clientX, ev.clientY);
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
      setStatus(`Player ${session.selected_player_id}`);
    } catch (e) {
      setStatus(e.message);
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
