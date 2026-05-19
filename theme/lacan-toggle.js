(function () {
  "use strict";

  var toggles = {
    original: "hide-original",
    notes: "hide-notes",
    commentary: "hide-commentary",
  };

  var shareState = {
    active: false,
    selected: {},
  };

  var qrLevels = {
    1: { blocks: [19], ecc: 7, align: [] },
    2: { blocks: [34], ecc: 10, align: [6, 18] },
    3: { blocks: [55], ecc: 15, align: [6, 22] },
    4: { blocks: [80], ecc: 20, align: [6, 26] },
    5: { blocks: [108], ecc: 26, align: [6, 30] },
    6: { blocks: [68, 68], ecc: 18, align: [6, 34] },
    7: { blocks: [78, 78], ecc: 20, align: [6, 22, 38] },
    8: { blocks: [97, 97], ecc: 24, align: [6, 24, 42] },
    9: { blocks: [116, 116], ecc: 30, align: [6, 26, 46] },
    10: { blocks: [68, 68, 69, 69], ecc: 18, align: [6, 28, 50] },
  };

  var qrExp = null;
  var qrLog = null;

  function key(name) {
    return "lacan-toggle-" + name;
  }

  function isEnabled(name) {
    var stored = window.localStorage.getItem(key(name));
    return stored === null ? true : stored === "true";
  }

  function applyToggle(name, enabled) {
    document.documentElement.classList.toggle(toggles[name], !enabled);
    var controls = document.querySelectorAll('[data-lacan-toggle="' + name + '"]');
    Array.prototype.forEach.call(controls, function (control) {
      control.checked = enabled;
    });
  }

  function applyAll() {
    Object.keys(toggles).forEach(function (name) {
      applyToggle(name, isEnabled(name));
    });
  }

  function dispatchSearchEvent(searchbar) {
    ["input", "keyup"].forEach(function (eventName) {
      searchbar.dispatchEvent(new Event(eventName, { bubbles: true }));
    });
  }

  function openBookSearch(query, focusSearchbar) {
    var searchbar = document.getElementById("mdbook-searchbar");
    if (!searchbar) {
      return false;
    }

    var toggle = document.getElementById("mdbook-search-toggle");
    var searchOuter = document.getElementById("mdbook-searchbar-outer");
    if (searchOuter && searchOuter.classList.contains("hidden") && toggle) {
      toggle.click();
    }

    searchbar.value = query;
    dispatchSearchEvent(searchbar);

    if (focusSearchbar) {
      searchbar.focus();
    }

    return true;
  }

  function createSearchForm() {
    var form = document.createElement("form");
    form.className = "lacan-tool-search";
    form.setAttribute("role", "search");

    var input = document.createElement("input");
    input.className = "lacan-tool-search-input";
    input.type = "search";
    input.placeholder = "搜索全文";
    input.setAttribute("aria-label", "搜索全文");

    var button = document.createElement("button");
    button.className = "lacan-tool-button";
    button.type = "submit";
    button.title = "搜索";
    button.textContent = "搜索";

    form.appendChild(input);
    form.appendChild(button);
    return form;
  }

  function createBackToTopButton() {
    var button = document.createElement("button");
    button.className = "lacan-tool-button lacan-back-to-top";
    button.type = "button";
    button.title = "回到页面最上方";
    button.setAttribute("aria-label", "回到页面最上方");
    button.textContent = "↑";
    return button;
  }

  function refineThemeMenu() {
    var labels = {
      default_theme: "自动",
      light: "浅色",
      navy: "暗色",
    };

    ["rust", "coal", "ayu"].forEach(function (name) {
      var button = document.getElementById("mdbook-theme-" + name);
      if (button && button.parentElement) {
        button.parentElement.remove();
      }
    });

    Object.keys(labels).forEach(function (name) {
      var button = document.getElementById("mdbook-theme-" + name);
      if (button) {
        button.textContent = labels[name];
      }
    });
  }

  function createShareControls() {
    var actions = document.createElement("div");
    actions.className = "lacan-share-actions";

    var toggle = document.createElement("button");
    toggle.className = "lacan-tool-button lacan-share-toggle";
    toggle.type = "button";
    toggle.title = "选择片段";
    toggle.setAttribute("aria-pressed", "false");
    toggle.textContent = "分享";

    var save = document.createElement("button");
    save.className = "lacan-tool-button lacan-share-save";
    save.type = "button";
    save.title = "保存选中片段图片";
    save.disabled = true;
    save.textContent = "保存图片";

    var clear = document.createElement("button");
    clear.className = "lacan-tool-button lacan-share-clear";
    clear.type = "button";
    clear.title = "清空选择";
    clear.textContent = "清空";

    var count = document.createElement("span");
    count.className = "lacan-share-count";
    count.setAttribute("aria-live", "polite");
    count.textContent = "已选 0";

    actions.appendChild(toggle);
    actions.appendChild(save);
    actions.appendChild(clear);
    actions.appendChild(count);
    return actions;
  }

  function getParagraphIds(section) {
    var ids = (section.getAttribute("data-paragraph-ids") || "").trim();
    if (!ids) {
      return section.id ? [section.id] : [];
    }
    return ids.split(/\s+/).filter(Boolean);
  }

  function getAnchorId(section) {
    var ids = getParagraphIds(section);
    return section.id || ids[0] || "";
  }

  function ensureParagraphAnchors(section) {
    var ids = getParagraphIds(section);
    if (!ids.length) {
      return;
    }

    if (!section.id) {
      section.id = ids[0];
    }

    ids.slice(1).forEach(function (id) {
      if (document.getElementById(id)) {
        return;
      }

      var alias = document.createElement("span");
      alias.id = id;
      alias.className = "paragraph-anchor-alias";
      alias.setAttribute("aria-hidden", "true");
      section.insertBefore(alias, section.firstChild);
    });
  }

  function ensureShareCheckbox(section) {
    ensureParagraphAnchors(section);

    if (section.querySelector(".lacan-share-select")) {
      return;
    }

    var ids = getParagraphIds(section);
    var labelText = ids.length ? ids.join(", ") : "当前片段";
    var paragraphId = section.querySelector(".paragraph-id");
    if (!paragraphId) {
      return;
    }

    var label = document.createElement("label");
    label.className = "lacan-share-select";

    var input = document.createElement("input");
    input.type = "checkbox";
    input.setAttribute("aria-label", "选择片段 " + labelText);

    input.addEventListener("change", function () {
      var anchorId = getAnchorId(section);
      if (!anchorId) {
        return;
      }

      if (input.checked) {
        shareState.selected[anchorId] = true;
      } else {
        delete shareState.selected[anchorId];
      }

      section.classList.toggle("lacan-share-selected", input.checked);
      updateShareControls();
    });

    label.appendChild(input);
    section.insertBefore(label, paragraphId);
  }

  function selectedSections() {
    var sections = document.querySelectorAll(".parallel-paragraph");
    var selected = [];
    Array.prototype.forEach.call(sections, function (section) {
      var anchorId = getAnchorId(section);
      if (anchorId && shareState.selected[anchorId]) {
        selected.push(section);
      }
    });
    return selected;
  }

  function selectedCount() {
    return selectedSections().length;
  }

  function updateShareControls() {
    var count = selectedCount();
    var toggle = document.querySelector(".lacan-share-toggle");
    var save = document.querySelector(".lacan-share-save");
    var clear = document.querySelector(".lacan-share-clear");
    var countLabel = document.querySelector(".lacan-share-count");

    document.documentElement.classList.toggle("lacan-share-mode", shareState.active);

    if (toggle) {
      toggle.textContent = shareState.active ? "退出分享" : "分享";
      toggle.setAttribute("aria-pressed", shareState.active ? "true" : "false");
    }

    if (save) {
      save.disabled = count === 0;
    }

    if (clear) {
      clear.disabled = count === 0;
    }

    if (countLabel) {
      countLabel.textContent = "已选 " + count;
    }
  }

  function clearShareSelection() {
    shareState.selected = {};
    var sections = document.querySelectorAll(".parallel-paragraph");
    Array.prototype.forEach.call(sections, function (section) {
      section.classList.remove("lacan-share-selected");
      var checkbox = section.querySelector(".lacan-share-select input");
      if (checkbox) {
        checkbox.checked = false;
      }
    });
    updateShareControls();
  }

  function enableShareMode() {
    var sections = document.querySelectorAll(".parallel-paragraph");
    Array.prototype.forEach.call(sections, ensureShareCheckbox);
    shareState.active = true;
    updateShareControls();
  }

  function disableShareMode() {
    shareState.active = false;
    updateShareControls();
  }

  function toggleShareMode() {
    if (shareState.active) {
      disableShareMode();
    } else {
      enableShareMode();
    }
  }

  function setupShareControls(controls) {
    var actions = controls.querySelector(".lacan-share-actions");
    if (!actions) {
      actions = createShareControls();
      controls.appendChild(actions);
    }

    var toggle = actions.querySelector(".lacan-share-toggle");
    var save = actions.querySelector(".lacan-share-save");
    var clear = actions.querySelector(".lacan-share-clear");

    if (toggle) {
      toggle.addEventListener("click", toggleShareMode);
    }

    if (save) {
      save.addEventListener("click", function () {
        try {
          saveSelectedParagraphs();
        } catch (error) {
          window.alert(error && error.message ? error.message : "保存图片失败。");
        }
      });
    }

    if (clear) {
      clear.addEventListener("click", clearShareSelection);
    }

    updateShareControls();
  }

  function ensureToolPanel() {
    var controls = document.querySelector(".reading-controls");
    if (!controls) {
      return;
    }

    controls.classList.add("lacan-tool-panel");

    var searchForm = controls.querySelector(".lacan-tool-search");
    if (!searchForm) {
      searchForm = createSearchForm();
      controls.appendChild(searchForm);
    }

    var searchInput = searchForm.querySelector(".lacan-tool-search-input");
    if (searchInput) {
      searchInput.addEventListener("input", function () {
        openBookSearch(searchInput.value, false);
      });

      searchForm.addEventListener("submit", function (event) {
        event.preventDefault();
        openBookSearch(searchInput.value, true);
      });
    }

    setupShareControls(controls);

    var backToTop = controls.querySelector(".lacan-back-to-top");
    if (!backToTop) {
      backToTop = createBackToTopButton();
      controls.appendChild(backToTop);
    }

    backToTop.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  function normalizeText(text) {
    return String(text || "")
      .replace(/\u00a0/g, " ")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n[ \t]+/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .replace(/[ \t]{2,}/g, " ")
      .trim();
  }

  function elementText(element) {
    if (!element) {
      return "";
    }
    return normalizeText(element.innerText || element.textContent || "");
  }

  function collectTexts(section, selector) {
    var parts = [];
    var nodes = section.querySelectorAll(selector);
    Array.prototype.forEach.call(nodes, function (node) {
      var text = elementText(node);
      if (text) {
        parts.push(text);
      }
    });
    return parts.join("\n\n");
  }

  function collectSnippet(section) {
    var ids = getParagraphIds(section);
    var snippet = {
      ids: ids,
      anchor: getAnchorId(section),
      url: buildParagraphUrl(section),
      blocks: [],
    };

    var translation = elementText(section.querySelector(".translation-block"));
    if (translation) {
      snippet.blocks.push({ label: "译文", text: translation });
    }

    if (!document.documentElement.classList.contains("hide-notes")) {
      var notes = collectTexts(section, ".note-block:not(.original-notes)");
      if (notes) {
        snippet.blocks.push({ label: "注释", text: notes });
      }
    }

    if (!document.documentElement.classList.contains("hide-commentary")) {
      var commentary = collectTexts(section, ".commentary-block");
      if (commentary) {
        snippet.blocks.push({ label: "个人解读", text: commentary });
      }
    }

    if (!document.documentElement.classList.contains("hide-original")) {
      var original = collectTexts(section, ".original-paragraph");
      if (original) {
        snippet.blocks.push({ label: "原文", text: original });
      }
    }

    return snippet;
  }

  function buildParagraphUrl(section) {
    var anchor = getAnchorId(section);
    // Derive from the current reader URL so QR codes work on any domain or subpath deployment.
    var url = new URL(window.location.href);
    url.search = "";
    url.hash = anchor || "";
    return url.toString();
  }

  function safeFilename(text) {
    return String(text || "fragment")
      .replace(/[^\w\u4e00-\u9fff-]+/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 96) || "fragment";
  }

  function wrapText(ctx, text, maxWidth) {
    var paragraphs = normalizeText(text).split(/\n+/);
    var lines = [];

    paragraphs.forEach(function (paragraph, paragraphIndex) {
      var line = "";
      var chars = paragraph.split("");

      chars.forEach(function (char) {
        var next = line + char;
        if (line && ctx.measureText(next).width > maxWidth) {
          lines.push(line);
          line = char.replace(/^\s+/, "");
        } else {
          line = next;
        }
      });

      if (line) {
        lines.push(line);
      }

      if (paragraphIndex < paragraphs.length - 1) {
        lines.push("");
      }
    });

    return lines.length ? lines : [""];
  }

  function addTextOp(ctx, ops, x, y, maxWidth, text, options) {
    ctx.font = options.font;
    var lines = wrapText(ctx, text, maxWidth);
    ops.push({
      type: "text",
      x: x,
      y: y,
      lines: lines,
      font: options.font,
      color: options.color,
      lineHeight: options.lineHeight,
    });
    return y + lines.length * options.lineHeight;
  }

  function createShareCanvas(snippets) {
    if (!snippets.length) {
      throw new Error("请先选择要分享的片段。");
    }

    var targetUrl = snippets[0].url;
    var qrMatrix = createQrMatrix(targetUrl);
    var scale = 2;
    var width = 1080;
    var padding = 64;
    var innerWidth = width - padding * 2;
    var measureCanvas = document.createElement("canvas");
    var measureCtx = measureCanvas.getContext("2d");
    var ops = [];
    var y = padding;
    var fontSans = '"PingFang SC","Noto Sans CJK SC","Microsoft YaHei",Arial,sans-serif';
    var fontSerif = '"Noto Serif CJK SC","Songti SC","SimSun",serif';
    var fontMono = 'Menlo,Consolas,"Liberation Mono",monospace';

    y = addTextOp(measureCtx, ops, padding, y, innerWidth, "拉康中文开放翻译计划", {
      font: "700 30px " + fontSans,
      color: "#1f2933",
      lineHeight: 42,
    });
    y += 4;
    y = addTextOp(measureCtx, ops, padding, y, innerWidth, "片段分享", {
      font: "18px " + fontSans,
      color: "#5d6673",
      lineHeight: 28,
    });
    y += 30;

    snippets.forEach(function (snippet, index) {
      if (index > 0) {
        ops.push({ type: "rule", x: padding, y: y, width: innerWidth });
        y += 28;
      }

      y = addTextOp(measureCtx, ops, padding, y, innerWidth, snippet.ids.join(", "), {
        font: "700 22px " + fontMono,
        color: "#2f6975",
        lineHeight: 34,
      });
      y += 10;

      if (!snippet.blocks.length) {
        y = addTextOp(measureCtx, ops, padding, y, innerWidth, "当前片段没有可导出的文本。", {
          font: "24px " + fontSerif,
          color: "#4a4f57",
          lineHeight: 40,
        });
        y += 18;
        return;
      }

      snippet.blocks.forEach(function (block) {
        y = addTextOp(measureCtx, ops, padding, y, innerWidth, block.label, {
          font: "700 19px " + fontSans,
          color: "#9c6b1f",
          lineHeight: 30,
        });
        y = addTextOp(measureCtx, ops, padding, y + 4, innerWidth, block.text, {
          font: "24px " + fontSerif,
          color: "#263238",
          lineHeight: 40,
        });
        y += 18;
      });
    });

    var qrSize = 174;
    var footerY = y + 20;
    var footerTextWidth = innerWidth - qrSize - 30;
    var footerTextY = footerY + 8;
    var footerLabel = snippets.length > 1 ? "扫码定位首段" : "扫码定位该段";
    footerTextY = addTextOp(measureCtx, ops, padding, footerTextY, footerTextWidth, footerLabel, {
      font: "700 20px " + fontSans,
      color: "#1f2933",
      lineHeight: 30,
    });
    addTextOp(measureCtx, ops, padding, footerTextY + 6, footerTextWidth, targetUrl, {
      font: "17px " + fontMono,
      color: "#5d6673",
      lineHeight: 27,
    });

    var height = Math.ceil(Math.max(footerY + qrSize, footerTextY + 70) + padding);
    var canvas = document.createElement("canvas");
    canvas.width = width * scale;
    canvas.height = height * scale;

    var ctx = canvas.getContext("2d");
    ctx.scale(scale, scale);
    ctx.textBaseline = "top";
    ctx.fillStyle = "#fbf8f1";
    ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(34, 34, width - 68, height - 68);
    ctx.strokeStyle = "#ded6c8";
    ctx.lineWidth = 1;
    ctx.strokeRect(34.5, 34.5, width - 69, height - 69);

    ops.forEach(function (op) {
      if (op.type === "rule") {
        ctx.strokeStyle = "#ded6c8";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(op.x, op.y + 0.5);
        ctx.lineTo(op.x + op.width, op.y + 0.5);
        ctx.stroke();
        return;
      }

      ctx.font = op.font;
      ctx.fillStyle = op.color;
      op.lines.forEach(function (line, lineIndex) {
        if (line) {
          ctx.fillText(line, op.x, op.y + lineIndex * op.lineHeight);
        }
      });
    });

    ctx.strokeStyle = "#ded6c8";
    ctx.beginPath();
    ctx.moveTo(padding, footerY - 20.5);
    ctx.lineTo(padding + innerWidth, footerY - 20.5);
    ctx.stroke();

    drawQr(ctx, qrMatrix, padding + innerWidth - qrSize, footerY, qrSize);
    return canvas;
  }

  function saveSelectedParagraphs() {
    var sections = selectedSections();
    if (!sections.length) {
      throw new Error("请先选择要分享的片段。");
    }

    var snippets = sections.map(collectSnippet);
    var canvas = createShareCanvas(snippets);
    var ids = snippets.map(function (snippet) {
      return snippet.anchor;
    }).join("-");
    var link = document.createElement("a");
    link.download = "lacan-" + safeFilename(ids) + ".png";
    link.href = canvas.toDataURL("image/png");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  function initGf() {
    if (qrExp && qrLog) {
      return;
    }

    qrExp = [];
    qrLog = [];

    var x = 1;
    for (var i = 0; i < 255; i += 1) {
      qrExp[i] = x;
      qrLog[x] = i;
      x <<= 1;
      if (x & 0x100) {
        x ^= 0x11d;
      }
    }

    for (var j = 255; j < 512; j += 1) {
      qrExp[j] = qrExp[j - 255];
    }
  }

  function gfMultiply(x, y) {
    if (x === 0 || y === 0) {
      return 0;
    }
    return qrExp[qrLog[x] + qrLog[y]];
  }

  function reedSolomonGenerator(degree) {
    initGf();
    var poly = [1];
    for (var i = 0; i < degree; i += 1) {
      var next = new Array(poly.length + 1);
      for (var n = 0; n < next.length; n += 1) {
        next[n] = 0;
      }
      for (var j = 0; j < poly.length; j += 1) {
        next[j] ^= poly[j];
        next[j + 1] ^= gfMultiply(poly[j], qrExp[i]);
      }
      poly = next;
    }
    return poly;
  }

  function reedSolomonRemainder(data, degree) {
    var generator = reedSolomonGenerator(degree);
    var remainder = new Array(degree);
    for (var i = 0; i < degree; i += 1) {
      remainder[i] = 0;
    }

    data.forEach(function (byte) {
      var factor = byte ^ remainder[0];
      remainder.shift();
      remainder.push(0);
      for (var j = 0; j < degree; j += 1) {
        remainder[j] ^= gfMultiply(generator[j + 1], factor);
      }
    });

    return remainder;
  }

  function appendBits(bits, value, length) {
    for (var i = length - 1; i >= 0; i -= 1) {
      bits.push(((value >>> i) & 1) !== 0);
    }
  }

  function sum(values) {
    return values.reduce(function (total, value) {
      return total + value;
    }, 0);
  }

  function chooseQrVersion(dataLength) {
    for (var version = 1; version <= 10; version += 1) {
      var level = qrLevels[version];
      var countBits = version <= 9 ? 8 : 16;
      var neededBits = 4 + countBits + dataLength * 8;
      if (neededBits <= sum(level.blocks) * 8) {
        return version;
      }
    }
    throw new Error("当前段落链接过长，无法生成二维码。");
  }

  function encodeQrData(text) {
    if (!window.TextEncoder) {
      throw new Error("当前浏览器不支持二维码编码所需的 TextEncoder。");
    }

    var bytes = Array.prototype.slice.call(new TextEncoder().encode(text));
    var version = chooseQrVersion(bytes.length);
    var level = qrLevels[version];
    var capacity = sum(level.blocks);
    var capacityBits = capacity * 8;
    var bits = [];

    appendBits(bits, 0x4, 4);
    appendBits(bits, bytes.length, version <= 9 ? 8 : 16);
    bytes.forEach(function (byte) {
      appendBits(bits, byte, 8);
    });

    var terminator = Math.min(4, capacityBits - bits.length);
    appendBits(bits, 0, terminator);
    while (bits.length % 8 !== 0) {
      bits.push(false);
    }

    var codewords = [];
    for (var i = 0; i < bits.length; i += 8) {
      var value = 0;
      for (var j = 0; j < 8; j += 1) {
        value = (value << 1) | (bits[i + j] ? 1 : 0);
      }
      codewords.push(value);
    }

    var padBytes = [0xec, 0x11];
    var padIndex = 0;
    while (codewords.length < capacity) {
      codewords.push(padBytes[padIndex % 2]);
      padIndex += 1;
    }

    return { version: version, level: level, codewords: codewords };
  }

  function splitBlocks(codewords, blockLengths) {
    var blocks = [];
    var offset = 0;
    blockLengths.forEach(function (length) {
      blocks.push(codewords.slice(offset, offset + length));
      offset += length;
    });
    return blocks;
  }

  function addErrorCorrection(encoded) {
    var dataBlocks = splitBlocks(encoded.codewords, encoded.level.blocks);
    var eccBlocks = dataBlocks.map(function (block) {
      return reedSolomonRemainder(block, encoded.level.ecc);
    });
    var result = [];
    var maxDataLength = Math.max.apply(null, encoded.level.blocks);

    for (var i = 0; i < maxDataLength; i += 1) {
      dataBlocks.forEach(function (block) {
        if (i < block.length) {
          result.push(block[i]);
        }
      });
    }

    for (var j = 0; j < encoded.level.ecc; j += 1) {
      eccBlocks.forEach(function (block) {
        result.push(block[j]);
      });
    }

    return result;
  }

  function createQrState(version) {
    var size = version * 4 + 17;
    var modules = [];
    var isFunction = [];
    for (var y = 0; y < size; y += 1) {
      modules[y] = [];
      isFunction[y] = [];
      for (var x = 0; x < size; x += 1) {
        modules[y][x] = false;
        isFunction[y][x] = false;
      }
    }
    return { version: version, size: size, modules: modules, isFunction: isFunction };
  }

  function setFunction(state, x, y, dark) {
    if (x < 0 || y < 0 || x >= state.size || y >= state.size) {
      return;
    }
    state.modules[y][x] = !!dark;
    state.isFunction[y][x] = true;
  }

  function drawFinder(state, x, y) {
    for (var dy = -1; dy <= 7; dy += 1) {
      for (var dx = -1; dx <= 7; dx += 1) {
        var xx = x + dx;
        var yy = y + dy;
        var dark = dx >= 0 && dx <= 6 && dy >= 0 && dy <= 6 &&
          (dx === 0 || dx === 6 || dy === 0 || dy === 6 || (dx >= 2 && dx <= 4 && dy >= 2 && dy <= 4));
        setFunction(state, xx, yy, dark);
      }
    }
  }

  function drawAlignment(state, cx, cy) {
    for (var dy = -2; dy <= 2; dy += 1) {
      for (var dx = -2; dx <= 2; dx += 1) {
        setFunction(state, cx + dx, cy + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
      }
    }
  }

  function reserveFormatBits(state) {
    drawFormatBits(state, 0);
  }

  function getBit(value, index) {
    return ((value >>> index) & 1) !== 0;
  }

  function drawFormatBits(state, mask) {
    var data = (1 << 3) | mask;
    var remainder = data;
    for (var i = 0; i < 10; i += 1) {
      remainder = (remainder << 1) ^ (((remainder >>> 9) & 1) ? 0x537 : 0);
    }
    var bits = ((data << 10) | remainder) ^ 0x5412;

    for (var a = 0; a <= 5; a += 1) {
      setFunction(state, 8, a, getBit(bits, a));
    }
    setFunction(state, 8, 7, getBit(bits, 6));
    setFunction(state, 8, 8, getBit(bits, 7));
    setFunction(state, 7, 8, getBit(bits, 8));
    for (var b = 9; b < 15; b += 1) {
      setFunction(state, 14 - b, 8, getBit(bits, b));
    }

    for (var c = 0; c < 8; c += 1) {
      setFunction(state, state.size - 1 - c, 8, getBit(bits, c));
    }
    for (var d = 8; d < 15; d += 1) {
      setFunction(state, 8, state.size - 15 + d, getBit(bits, d));
    }
    setFunction(state, 8, state.size - 8, true);
  }

  function drawVersionBits(state) {
    if (state.version < 7) {
      return;
    }

    var remainder = state.version;
    for (var i = 0; i < 12; i += 1) {
      remainder = (remainder << 1) ^ (((remainder >>> 11) & 1) ? 0x1f25 : 0);
    }
    var bits = (state.version << 12) | remainder;

    for (var j = 0; j < 18; j += 1) {
      var bit = getBit(bits, j);
      var a = state.size - 11 + (j % 3);
      var b = Math.floor(j / 3);
      setFunction(state, a, b, bit);
      setFunction(state, b, a, bit);
    }
  }

  function drawFunctionPatterns(state, alignPositions) {
    drawFinder(state, 0, 0);
    drawFinder(state, state.size - 7, 0);
    drawFinder(state, 0, state.size - 7);

    for (var i = 8; i < state.size - 8; i += 1) {
      setFunction(state, i, 6, i % 2 === 0);
      setFunction(state, 6, i, i % 2 === 0);
    }

    alignPositions.forEach(function (cx) {
      alignPositions.forEach(function (cy) {
        var nearFinder = (cx < 9 && cy < 9) ||
          (cx > state.size - 10 && cy < 9) ||
          (cx < 9 && cy > state.size - 10);
        if (!nearFinder) {
          drawAlignment(state, cx, cy);
        }
      });
    });

    reserveFormatBits(state);
    drawVersionBits(state);
  }

  function placeDataBits(state, codewords) {
    var bitLength = codewords.length * 8;
    var bitIndex = 0;
    var upward = true;

    for (var right = state.size - 1; right >= 1; right -= 2) {
      if (right === 6) {
        right = 5;
      }

      for (var vert = 0; vert < state.size; vert += 1) {
        var y = upward ? state.size - 1 - vert : vert;
        for (var j = 0; j < 2; j += 1) {
          var x = right - j;
          if (state.isFunction[y][x]) {
            continue;
          }

          var dark = false;
          if (bitIndex < bitLength) {
            dark = ((codewords[bitIndex >>> 3] >>> (7 - (bitIndex & 7))) & 1) !== 0;
          }
          state.modules[y][x] = dark;
          bitIndex += 1;
        }
      }

      upward = !upward;
    }
  }

  function maskBit(mask, x, y) {
    switch (mask) {
      case 0: return (x + y) % 2 === 0;
      case 1: return y % 2 === 0;
      case 2: return x % 3 === 0;
      case 3: return (x + y) % 3 === 0;
      case 4: return (Math.floor(y / 2) + Math.floor(x / 3)) % 2 === 0;
      case 5: return ((x * y) % 2 + (x * y) % 3) === 0;
      case 6: return (((x * y) % 2 + (x * y) % 3) % 2) === 0;
      case 7: return (((x + y) % 2 + (x * y) % 3) % 2) === 0;
      default: return false;
    }
  }

  function cloneQrState(state) {
    var clone = createQrState(state.version);
    for (var y = 0; y < state.size; y += 1) {
      for (var x = 0; x < state.size; x += 1) {
        clone.modules[y][x] = state.modules[y][x];
        clone.isFunction[y][x] = state.isFunction[y][x];
      }
    }
    return clone;
  }

  function applyMask(state, mask) {
    var masked = cloneQrState(state);
    for (var y = 0; y < masked.size; y += 1) {
      for (var x = 0; x < masked.size; x += 1) {
        if (!masked.isFunction[y][x] && maskBit(mask, x, y)) {
          masked.modules[y][x] = !masked.modules[y][x];
        }
      }
    }
    drawFormatBits(masked, mask);
    return masked;
  }

  function penaltyScore(state) {
    var penalty = 0;
    var size = state.size;

    function scoreLine(getValue) {
      var score = 0;
      var runColor = getValue(0);
      var runLength = 1;
      for (var i = 1; i < size; i += 1) {
        var color = getValue(i);
        if (color === runColor) {
          runLength += 1;
          if (runLength === 5) {
            score += 3;
          } else if (runLength > 5) {
            score += 1;
          }
        } else {
          runColor = color;
          runLength = 1;
        }
      }
      return score;
    }

    for (var y = 0; y < size; y += 1) {
      penalty += scoreLine(function (x) {
        return state.modules[y][x];
      });
    }
    for (var x = 0; x < size; x += 1) {
      penalty += scoreLine(function (yIndex) {
        return state.modules[yIndex][x];
      });
    }

    for (var yy = 0; yy < size - 1; yy += 1) {
      for (var xx = 0; xx < size - 1; xx += 1) {
        var color = state.modules[yy][xx];
        if (color === state.modules[yy][xx + 1] &&
            color === state.modules[yy + 1][xx] &&
            color === state.modules[yy + 1][xx + 1]) {
          penalty += 3;
        }
      }
    }

    var pattern = [true, false, true, true, true, false, true, false, false, false, false];
    var reverse = pattern.slice().reverse();
    function matchesPattern(getValue, start, values) {
      for (var i = 0; i < values.length; i += 1) {
        if (getValue(start + i) !== values[i]) {
          return false;
        }
      }
      return true;
    }
    for (var row = 0; row < size; row += 1) {
      for (var sx = 0; sx <= size - 11; sx += 1) {
        if (matchesPattern(function (index) { return state.modules[row][index]; }, sx, pattern) ||
            matchesPattern(function (index) { return state.modules[row][index]; }, sx, reverse)) {
          penalty += 40;
        }
      }
    }
    for (var col = 0; col < size; col += 1) {
      for (var sy = 0; sy <= size - 11; sy += 1) {
        if (matchesPattern(function (index) { return state.modules[index][col]; }, sy, pattern) ||
            matchesPattern(function (index) { return state.modules[index][col]; }, sy, reverse)) {
          penalty += 40;
        }
      }
    }

    var dark = 0;
    for (var py = 0; py < size; py += 1) {
      for (var px = 0; px < size; px += 1) {
        if (state.modules[py][px]) {
          dark += 1;
        }
      }
    }
    var ratio = Math.abs((dark * 100) / (size * size) - 50);
    penalty += Math.floor(ratio / 5) * 10;
    return penalty;
  }

  function createQrMatrix(text) {
    var encoded = encodeQrData(text);
    var codewords = addErrorCorrection(encoded);
    var base = createQrState(encoded.version);
    drawFunctionPatterns(base, encoded.level.align);
    placeDataBits(base, codewords);

    var best = null;
    var bestPenalty = Infinity;
    for (var mask = 0; mask < 8; mask += 1) {
      var candidate = applyMask(base, mask);
      var penalty = penaltyScore(candidate);
      if (penalty < bestPenalty) {
        best = candidate;
        bestPenalty = penalty;
      }
    }
    return best.modules;
  }

  function drawQr(ctx, matrix, x, y, size) {
    var quiet = 4;
    var count = matrix.length;
    var moduleSize = size / (count + quiet * 2);

    ctx.fillStyle = "#ffffff";
    ctx.fillRect(x, y, size, size);
    ctx.fillStyle = "#111827";

    for (var row = 0; row < count; row += 1) {
      for (var col = 0; col < count; col += 1) {
        if (matrix[row][col]) {
          ctx.fillRect(
            x + (col + quiet) * moduleSize,
            y + (row + quiet) * moduleSize,
            Math.ceil(moduleSize),
            Math.ceil(moduleSize)
          );
        }
      }
    }

    ctx.strokeStyle = "#ded6c8";
    ctx.strokeRect(x + 0.5, y + 0.5, size - 1, size - 1);
  }

  document.addEventListener("DOMContentLoaded", function () {
    refineThemeMenu();
    ensureToolPanel();
    applyAll();

    Array.prototype.forEach.call(document.querySelectorAll(".parallel-paragraph"), function (section) {
      ensureParagraphAnchors(section);
    });

    Object.keys(toggles).forEach(function (name) {
      var controls = document.querySelectorAll('[data-lacan-toggle="' + name + '"]');
      Array.prototype.forEach.call(controls, function (control) {
        control.addEventListener("change", function () {
          window.localStorage.setItem(key(name), String(control.checked));
          applyToggle(name, control.checked);
        });
      });
    });
  });
})();
