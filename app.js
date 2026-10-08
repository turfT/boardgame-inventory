const state = {
  games: [],
  filtered: [],
  selected: [],
  inventories: [],
};

const $ = (id) => document.getElementById(id);
const controls = {
  search: $("searchInput"), players: $("playerFilter"), bestPlayers: $("bestPlayerFilter"),
  time: $("timeFilter"), weight: $("weightFilter"),
  rating: $("ratingFilter"), type: $("typeFilter"), mechanic: $("mechanicFilter"),
  owner: $("ownerFilter"), recent: $("recentFilter"), sort: $("sortSelect"),
};

const collator = new Intl.Collator("zh-CN", { numeric: true, sensitivity: "base" });
let toastTimer;

function showToast(message) {
  const toast = $("toast");
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 2600);
}

function addOptions(select, values) {
  values.filter(Boolean).sort((a, b) => collator.compare(String(a), String(b))).forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  });
}

function uniqueFlat(key) {
  return [...new Set(state.games.flatMap((game) => Array.isArray(game[key]) ? game[key] : [game[key]]))];
}

function populateFilters() {
  addOptions(controls.players, ["1","2","3","4","5","6","7","8","9","10","11+"]);
  addOptions(controls.bestPlayers, uniqueFlat("bestPlayers"));
  addOptions(controls.type, uniqueFlat("types"));
  addOptions(controls.mechanic, uniqueFlat("mechanics"));
  state.inventories.forEach((inventory) => {
    const option = document.createElement("option");
    option.value = inventory.id;
    option.textContent = `${inventory.name}（${inventory.count}）`;
    controls.owner.append(option);
  });
}

function inRange(value, rangeText) {
  if (!rangeText) return true;
  const [minimum, maximum] = rangeText.split("-").map(Number);
  return Number.isFinite(value) && value >= minimum && value <= maximum;
}

function updateTime(value) {
  const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  return match ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])).getTime() : 0;
}

function isRecentlyUpdated(game, days = 14) {
  const timestamp = updateTime(game.updatedAt);
  if (!timestamp) return false;
  const age = Date.now() - timestamp;
  return age >= 0 && age <= days * 24 * 60 * 60 * 1000;
}

function applyFilters() {
  const query = controls.search.value.trim().toLocaleLowerCase("zh-CN");
  const ratingMinimum = Number(controls.rating.value || 0);
  const filtered = state.games.filter((game) => {
    const nameMatch = !query || `${game.name} ${game.originalName || ""}`.toLocaleLowerCase("zh-CN").includes(query);
    return nameMatch
      && (!controls.owner.value || game.ownerIds.includes(controls.owner.value))
      && (!controls.players.value || (controls.players.value === "11+"
        ? game.supportedPlayers.some((value) => Number(value) >= 11)
        : game.supportedPlayers.includes(controls.players.value)))
      && (!controls.bestPlayers.value || game.bestPlayers.includes(controls.bestPlayers.value))
      && inRange(game.playingTime, controls.time.value)
      && inRange(game.weight, controls.weight.value)
      && (!ratingMinimum || game.rating >= ratingMinimum)
      && (!controls.type.value || game.types.includes(controls.type.value))
      && (!controls.mechanic.value || game.mechanics.includes(controls.mechanic.value))
      && (!controls.recent.value || isRecentlyUpdated(game, Number(controls.recent.value)));
  });

  const sorters = {
    name: (a,b) => collator.compare(a.name,b.name),
    "rating-desc": (a,b) => (b.rating || -1) - (a.rating || -1) || collator.compare(a.name,b.name),
    "rank-asc": (a,b) => (a.rank || Number.MAX_SAFE_INTEGER) - (b.rank || Number.MAX_SAFE_INTEGER),
    "weight-asc": (a,b) => (a.weight || Number.MAX_SAFE_INTEGER) - (b.weight || Number.MAX_SAFE_INTEGER),
    "time-asc": (a,b) => (a.playingTime || Number.MAX_SAFE_INTEGER) - (b.playingTime || Number.MAX_SAFE_INTEGER),
    "updated-desc": (a,b) => updateTime(b.updatedAt) - updateTime(a.updatedAt) || collator.compare(a.name,b.name),
  };
  state.filtered = filtered.sort(sorters[controls.sort.value]);
  renderGames();
}

function cardMeta(game) {
  const entries = [];
  if (game.players) entries.push(`<span><strong>${game.players}</strong> 人</span>`);
  if (game.playingTime) entries.push(`<span><strong>${game.playingTime}</strong> 分钟</span>`);
  if (game.weight) entries.push(`<span>重度 <strong>${game.weight.toFixed(2)}</strong></span>`);
  if (game.rating) entries.push(`<span>评分 <strong>${game.rating.toFixed(1)}</strong></span>`);
  return entries.join("");
}

function renderGames() {
  const grid = $("gameGrid");
  grid.replaceChildren();
  const fragment = document.createDocumentFragment();
  state.filtered.forEach((game) => {
    const selected = state.selected.includes(game.id);
    const article = document.createElement("article");
    article.className = `game-card${selected ? " selected" : ""}`;
    const cover = game.cover
      ? `<img src="${game.cover}" alt="${escapeHtml(game.name)}封面" loading="lazy" />`
      : `<div class="cover-placeholder" aria-hidden="true">北关</div>`;
    const bggUrl = game.bggId ? `https://boardgamegeek.com/boardgame/${encodeURIComponent(game.bggId)}` : "";
    const contentStart = bggUrl ? `<a class="game-link" href="${bggUrl}" target="_blank" rel="noopener noreferrer" aria-label="在 BGG 查看 ${escapeHtml(game.name)}">` : `<div class="game-link">`;
    const contentEnd = bggUrl ? "</a>" : "</div>";
    article.innerHTML = `
      ${contentStart}<div class="cover-wrap">
        ${cover}
        ${game.rank ? `<span class="rank-badge">BGG #${game.rank}</span>` : ""}
        ${isRecentlyUpdated(game) ? `<span class="recent-badge">最近更新</span>` : ""}
      </div>
      <div class="card-body">
        <h2 class="game-name" title="${escapeHtml(game.name)}">${escapeHtml(game.name)}</h2>
        <div class="meta-line">${cardMeta(game)}</div>
        <div class="tag-line">${game.types.slice(0,2).map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</div>
        <div class="owner-line">库存：${game.ownerNames.map(escapeHtml).join("、")}</div>
      </div>${contentEnd}
      <button class="select-game" type="button" aria-label="${selected ? "移出" : "加入"}候选清单">${selected ? "✓" : "+"}</button>`;
    article.querySelector(".select-game").addEventListener("click", () => toggleSelection(game.id));
    fragment.append(article);
  });
  grid.append(fragment);
  $("resultSummary").textContent = `找到 ${state.filtered.length} 款 · 库存共 ${state.games.length} 款`;
  const query = controls.search.value.trim();
  $("searchFeedback").textContent = query
    ? `“${query}”找到 ${state.filtered.length} 款桌游`
    : "输入名称即可即时查询";
  $("emptyState").hidden = state.filtered.length > 0;
}

function toggleSelection(id) {
  const index = state.selected.indexOf(id);
  if (index >= 0) state.selected.splice(index,1);
  else if (state.selected.length >= 5) return showToast("每次最多选择 5 款桌游");
  else state.selected.push(id);
  renderGames();
  renderSelection();
}

function gameById(id) { return state.games.find((game) => game.id === id); }

function moveSelection(id, delta) {
  const index = state.selected.indexOf(id);
  const next = index + delta;
  if (index < 0 || next < 0 || next >= state.selected.length) return;
  [state.selected[index], state.selected[next]] = [state.selected[next], state.selected[index]];
  renderSelection();
}

function renderSelection() {
  const list = $("selectedList");
  list.replaceChildren();
  state.selected.forEach((id, index) => {
    const game = gameById(id);
    const item = document.createElement("li");
    item.className = "selected-item";
    item.draggable = true;
    item.dataset.id = id;
    item.innerHTML = `
      <span class="drag-handle" aria-label="拖动排序">⋮⋮</span>
      ${game.cover ? `<img src="${game.cover}" alt="" />` : `<span class="selected-thumb"></span>`}
      <span class="selected-name">${escapeHtml(game.name)}</span>
      <span class="reorder-buttons">
        <button class="mini-button move-up" type="button" aria-label="上移" ${index === 0 ? "disabled" : ""}>↑</button>
        <button class="mini-button move-down" type="button" aria-label="下移" ${index === state.selected.length - 1 ? "disabled" : ""}>↓</button>
      </span>`;
    item.querySelector(".move-up").addEventListener("click", () => moveSelection(id,-1));
    item.querySelector(".move-down").addEventListener("click", () => moveSelection(id,1));
    item.addEventListener("dragstart", (event) => {
      event.dataTransfer.setData("text/plain", id);
      item.classList.add("dragging");
    });
    item.addEventListener("dragend", () => item.classList.remove("dragging"));
    item.addEventListener("dragover", (event) => {
      event.preventDefault();
      const movingId = event.dataTransfer.getData("text/plain");
      const from = state.selected.indexOf(movingId);
      const to = state.selected.indexOf(id);
      if (from >= 0 && to >= 0 && from !== to) {
        state.selected.splice(to, 0, state.selected.splice(from,1)[0]);
        renderSelection();
      }
    });
    list.append(item);
  });
  $("selectionCount").textContent = state.selected.length;
  $("selectionEmpty").hidden = state.selected.length > 0;
  $("exportPoster").disabled = state.selected.length === 0;
}

function openSelection() {
  $("selectionBackdrop").hidden = false;
  $("selectionPanel").hidden = false;
  document.body.style.overflow = "hidden";
  $("posterTitle").focus();
}

function closeSelection() {
  $("selectionBackdrop").hidden = true;
  $("selectionPanel").hidden = true;
  document.body.style.overflow = "";
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>'"]/g, (character) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[character]);
}

function loadImage(src) {
  return new Promise((resolve) => {
    if (!src) return resolve(null);
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => resolve(null);
    image.src = src;
  });
}

function roundedRect(context, x, y, width, height, radius) {
  context.beginPath();
  context.roundRect(x,y,width,height,radius);
  context.fill();
}

function wrapText(context, text, x, y, maxWidth, lineHeight, maxLines = 2) {
  const characters = [...String(text)];
  let line = "";
  let lineNumber = 0;
  for (let index = 0; index < characters.length; index += 1) {
    const test = line + characters[index];
    if (context.measureText(test).width > maxWidth && line) {
      context.fillText(line, x, y + lineNumber * lineHeight);
      line = characters[index];
      lineNumber += 1;
      if (lineNumber === maxLines - 1) {
        const rest = line + characters.slice(index + 1).join("");
        let fitted = rest;
        while (context.measureText(`${fitted}…`).width > maxWidth && fitted.length) fitted = fitted.slice(0,-1);
        context.fillText(`${fitted}…`, x, y + lineNumber * lineHeight);
        return;
      }
    } else line = test;
  }
  context.fillText(line, x, y + lineNumber * lineHeight);
}

async function exportPoster() {
  const games = state.selected.map(gameById).filter(Boolean);
  if (!games.length) return;
  const button = $("exportPoster");
  button.disabled = true;
  $("exportStatus").textContent = "正在生成长图…";
  try {
    const width = 1080;
    const headerHeight = 310;
    const cardHeight = 350;
    const gap = 28;
    const footerHeight = 190;
    const height = headerHeight + games.length * (cardHeight + gap) + footerHeight;
    const canvas = $("posterCanvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    const gradient = context.createLinearGradient(0,0,0,height);
    gradient.addColorStop(0,"#261a14");
    gradient.addColorStop(.18,"#4a2e20");
    gradient.addColorStop(1,"#efe1cc");
    context.fillStyle = gradient;
    context.fillRect(0,0,width,height);

    context.fillStyle = "#d48148";
    context.fillRect(72,70,14,150);
    context.fillStyle = "#f9edda";
    context.font = '700 72px "PingFang SC", sans-serif';
    wrapText(context, $("posterTitle").value.trim() || "让我们开桌游", 112, 128, 840, 84, 2);
    context.fillStyle = "#d9bda3";
    context.font = '28px "PingFang SC", sans-serif';
    context.fillText(`北关据点 · ${games.length} 款候选`,112,252);

    const [images, qrImage] = await Promise.all([
      Promise.all(games.map((game) => loadImage(game.cover))),
      loadImage("public/site-qr.png"),
    ]);
    games.forEach((game,index) => {
      const y = headerHeight + index * (cardHeight + gap);
      context.fillStyle = "#fffaf0";
      roundedRect(context,58,y,964,cardHeight,28);
      const image = images[index];
      const imageBox = {x:82,y:y+24,w:250,h:302};
      context.fillStyle = "#e5d8c6";
      roundedRect(context,imageBox.x,imageBox.y,imageBox.w,imageBox.h,20);
      if (image) {
        const ratio = Math.min(imageBox.w / image.width, imageBox.h / image.height);
        const drawWidth = image.width * ratio;
        const drawHeight = image.height * ratio;
        context.drawImage(image,imageBox.x+(imageBox.w-drawWidth)/2,imageBox.y+(imageBox.h-drawHeight)/2,drawWidth,drawHeight);
      }
      context.fillStyle = "#a94d2d";
      context.font = '700 28px Georgia, serif';
      context.fillText(String(index+1).padStart(2,"0"),370,y+62);
      context.fillStyle = "#2b211c";
      context.font = '700 42px "PingFang SC", sans-serif';
      wrapText(context,game.name,370,y+118,600,54,2);
      context.fillStyle = "#715f52";
      context.font = '28px "PingFang SC", sans-serif';
      const detail = [game.players ? `${game.players} 人` : "", game.playingTime ? `${game.playingTime} 分钟` : "", game.weight ? `重度 ${game.weight.toFixed(2)}` : ""].filter(Boolean).join("  ·  ");
      context.fillText(detail,370,y+230);
      const rating = game.rating ? `BGG ${game.rating.toFixed(1)}` : "";
      const ranking = game.rank ? `排名 #${game.rank}` : "";
      context.fillStyle = "#a94d2d";
      context.font = '700 27px "PingFang SC", sans-serif';
      context.fillText([rating,ranking].filter(Boolean).join("  ·  "),370,y+282);
    });

    if (qrImage) context.drawImage(qrImage,72,height-142,104,104);
    context.fillStyle = "#493226";
    context.font = '700 30px Georgia, "Songti SC", serif';
    context.fillText("北关据点库存查询",204,height-100);
    context.fillStyle = "#816b5d";
    context.font = '22px "PingFang SC", sans-serif';
    context.fillText("扫码查看完整库存",204,height-62);
    context.textAlign = "right";
    context.fillText(new Intl.DateTimeFormat("zh-CN",{dateStyle:"long"}).format(new Date()),1008,height-78);
    context.textAlign = "left";

    const blob = await new Promise((resolve) => canvas.toBlob(resolve,"image/png"));
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `北关据点-桌游候选-${new Date().toISOString().slice(0,10)}.png`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href),1000);
    $("exportStatus").textContent = "长图已生成，可以发送到通讯软件。";
  } catch (error) {
    console.error(error);
    $("exportStatus").textContent = "生成失败，请刷新页面后重试。";
  } finally {
    button.disabled = state.selected.length === 0;
  }
}

function resetFilters() {
  Object.values(controls).forEach((control) => {
    if (control.tagName === "INPUT") control.value = "";
    else control.selectedIndex = 0;
  });
  applyFilters();
}

async function initialize() {
  try {
    const response = await fetch("public/data/inventories.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const manifest = await response.json();
    const loaded = await Promise.all((manifest.inventories || []).map(async (inventory) => {
      const inventoryResponse = await fetch(inventory.file, { cache: "no-store" });
      if (!inventoryResponse.ok) throw new Error(`${inventory.file}: HTTP ${inventoryResponse.status}`);
      return { inventory, payload: await inventoryResponse.json() };
    }));
    state.inventories = loaded.map(({inventory, payload}) => ({
      ...inventory,
      count: (payload.games || []).filter((game) => /^\d+$/.test(String(game.bggId || ""))).length,
    }));
    const merged = new Map();
    loaded.forEach(({ inventory, payload }) => (payload.games || [])
      .filter((game) => /^\d+$/.test(String(game.bggId || "")))
      .forEach((rawGame) => {
      const mergeKey = `bgg:${rawGame.bggId}`;
      const existing = merged.get(mergeKey);
      if (existing) {
        existing.ownerIds.push(inventory.id);
        existing.ownerNames.push(inventory.name);
        if (updateTime(rawGame.updatedAt) > updateTime(existing.updatedAt)) existing.updatedAt = rawGame.updatedAt;
      } else {
        merged.set(mergeKey, {
          ...rawGame,
          id: mergeKey,
          supportedPlayers: rawGame.supportedPlayers || [],
          bestPlayers: rawGame.bestPlayers || [],
          types: rawGame.types || [],
          mechanics: rawGame.mechanics || [],
          ownerIds: [inventory.id],
          ownerNames: [inventory.name],
        });
      }
    }));
    state.games = [...merged.values()];
    const recentCount = state.games.filter((game) => isRecentlyUpdated(game)).length;
    controls.recent.options[1].textContent = `最近两周（${recentCount}）`;
    populateFilters();
    applyFilters();
  } catch (error) {
    console.error(error);
    $("resultSummary").textContent = "库存暂时无法读取";
    $("emptyState").hidden = false;
    $("emptyState").querySelector("h2").textContent = "库存读取失败";
    $("emptyState").querySelector("p").textContent = "请稍后刷新页面。";
  }
}

Object.values(controls).forEach((control) => control.addEventListener(control === controls.search ? "input" : "change", applyFilters));
$("searchForm").addEventListener("submit", (event) => { event.preventDefault(); applyFilters(); });
$("resetFilters").addEventListener("click", resetFilters);
$("openSelection").addEventListener("click", openSelection);
$("closeSelection").addEventListener("click", closeSelection);
$("selectionBackdrop").addEventListener("click", closeSelection);
$("clearSelection").addEventListener("click", () => { state.selected = []; renderGames(); renderSelection(); });
$("exportPoster").addEventListener("click", exportPoster);
document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !$("selectionPanel").hidden) closeSelection(); });

initialize();
