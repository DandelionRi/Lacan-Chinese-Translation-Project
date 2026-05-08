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

  document.addEventListener("DOMContentLoaded", function () {
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
