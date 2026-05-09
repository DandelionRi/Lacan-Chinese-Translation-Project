(function () {
  "use strict";

  var toggles = {
    original: "hide-original",
    notes: "hide-notes",
    commentary: "hide-commentary",
  };

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

    var backToTop = controls.querySelector(".lacan-back-to-top");
    if (!backToTop) {
      backToTop = createBackToTopButton();
      controls.appendChild(backToTop);
    }

    backToTop.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    ensureToolPanel();
    applyAll();

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
