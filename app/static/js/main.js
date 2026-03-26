// ── Mobile nav toggle ─────────────────────────────────────────────────────────
const navToggle = document.getElementById("navToggle");
const navMobile = document.getElementById("navMobile");
if (navToggle && navMobile) {
  navToggle.addEventListener("click", () => {
    navMobile.classList.toggle("open");
  });
}

// ── Unit dropdown toggle ──────────────────────────────────────────────────────
const unitBtn = document.getElementById("unitDropdownBtn");
const unitMenu = document.getElementById("unitDropdownMenu");

if (unitBtn && unitMenu) {
  unitBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    unitMenu.classList.toggle("open");
  });

  document.addEventListener("click", (e) => {
    if (!unitBtn.contains(e.target) && !unitMenu.contains(e.target)) {
      unitMenu.classList.remove("open");
    }
  });
}

// ── User dropdown toggle ──────────────────────────────────────────────────────
const userBtn = document.getElementById("userMenuBtn");
const userMenu = document.getElementById("userMenuDropdown");

if (userBtn && userMenu) {
  userBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    userMenu.classList.toggle("open");
  });

  document.addEventListener("click", (e) => {
    if (!userBtn.contains(e.target) && !userMenu.contains(e.target)) {
      userMenu.classList.remove("open");
    }
  });
}

// ── Auto-dismiss flash messages after 5 seconds ───────────────────────────────
document.querySelectorAll(".flash").forEach((el) => {
  setTimeout(() => {
    el.style.transition = "opacity 0.4s ease";
    el.style.opacity = "0";
    setTimeout(() => el.remove(), 400);
  }, 5000);
});

// ── Response toggle highlight (muster roll) ───────────────────────────────────
document.querySelectorAll(".response-option").forEach((label) => {
  label.querySelector("input")?.addEventListener("change", () => {
    document.querySelectorAll(".response-option").forEach((l) => l.classList.remove("response-selected"));
    label.classList.add("response-selected");
  });
});
