(function () {
  "use strict";

  // Mobile menus
  function toggle(btnId, targetSel) {
    var btn = document.getElementById(btnId), target = document.querySelector(targetSel);
    if (!btn || !target) return;
    btn.addEventListener("click", function () {
      var open = target.classList.toggle("open");
      btn.setAttribute("aria-expanded", open);
    });
  }
  toggle("menu-btn", ".navlinks");
  toggle("admin-menu-btn", ".sidebar");

  // Confirm dangerous actions
  document.addEventListener("submit", function (e) {
    var msg = e.target.getAttribute("data-confirm");
    if (msg && !window.confirm(msg)) { e.preventDefault(); return; }
    // Loading state + double-submit protection
    var btn = e.target.querySelector("button[type=submit]");
    if (btn && !e.defaultPrevented) {
      setTimeout(function () { btn.disabled = true; btn.classList.add("loading"); }, 0);
    }
  });

  // Booking page
  var form = document.getElementById("booking-form");
  if (!form) return;
  var serviceSel = document.getElementById("service_id"),
      staffSel = document.getElementById("staff_id"),
      dateIn = document.getElementById("date"),
      slotsBox = document.getElementById("slots"),
      startIn = document.getElementById("start"),
      submit = document.getElementById("book-submit"),
      summary = document.getElementById("summary"),
      staffData = JSON.parse(form.getAttribute("data-staff") || "[]"),
      slotsUrl = form.getAttribute("data-slots-url"),
      reqId = 0;

  function filterStaff() {
    var sid = parseInt(serviceSel.value, 10);
    Array.prototype.forEach.call(staffSel.options, function (opt) {
      if (!opt.value) return;
      var s = staffData.filter(function (x) { return String(x.id) === opt.value; })[0];
      var ok = s && s.services.indexOf(sid) !== -1;
      opt.hidden = !ok; opt.disabled = !ok;
      if (!ok && staffSel.value === opt.value) staffSel.value = "";
    });
  }

  function message(text) {
    slotsBox.innerHTML = "";
    var p = document.createElement("p");
    p.className = "muted"; p.textContent = text; slotsBox.appendChild(p);
  }

  function loadSlots() {
    startIn.value = ""; submit.disabled = true; summary.hidden = true;
    if (!serviceSel.value || !dateIn.value) { message("Choose a service and a date to see available times."); return; }
    var id = ++reqId;
    slotsBox.innerHTML = ""; slotsBox.setAttribute("aria-busy", "true");
    for (var i = 0; i < 8; i++) { var d = document.createElement("div"); d.className = "skeleton"; slotsBox.appendChild(d); }
    var qs = "service_id=" + encodeURIComponent(serviceSel.value) + "&date=" + encodeURIComponent(dateIn.value) +
      (staffSel.value ? "&staff_id=" + encodeURIComponent(staffSel.value) : "");
    fetch(slotsUrl + "?" + qs, { headers: { Accept: "application/json" } })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (id !== reqId) return;
        slotsBox.removeAttribute("aria-busy");
        if (!res.ok) { message(res.j.error || "Could not load times."); return; }
        if (!res.j.slots.length) { message("No available times on this day. Try another date or staff member."); return; }
        slotsBox.innerHTML = "";
        res.j.slots.forEach(function (s) {
          var b = document.createElement("button");
          b.type = "button"; b.className = "slot-btn"; b.textContent = s.label; b.setAttribute("aria-pressed", "false");
          b.addEventListener("click", function () {
            Array.prototype.forEach.call(slotsBox.children, function (c) { c.setAttribute("aria-pressed", "false"); });
            b.setAttribute("aria-pressed", "true");
            startIn.value = s.start; submit.disabled = false;
            var opt = serviceSel.options[serviceSel.selectedIndex];
            summary.hidden = false;
            summary.textContent = opt.getAttribute("data-name") + " · " + dateIn.value + " at " + s.label +
              " · " + opt.getAttribute("data-price");
          });
          slotsBox.appendChild(b);
        });
      })
      .catch(function () { if (id === reqId) message("Network error. Please try again."); });
  }

  serviceSel.addEventListener("change", function () { filterStaff(); loadSlots(); });
  staffSel.addEventListener("change", loadSlots);
  dateIn.addEventListener("change", loadSlots);
  filterStaff(); loadSlots();
})();
