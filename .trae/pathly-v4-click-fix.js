// Keep the v4 navigation action independent from the main delegated handlers.
document.addEventListener("pointerdown", (event) => {
  const button = event.target.closest?.('[data-daily-stage="lecture-v4"]');
  if (!button || button.disabled) return;
  event.preventDefault();
  if (typeof window.setDailyStage === "function") window.setDailyStage("lecture-v4");
}, true);
