(function () {
  const timer = document.getElementById("timer");
  const form = document.getElementById("exam-form");
  if (!timer || !form) return;

  let dirty = false;
  form.addEventListener("change", () => {
    dirty = true;
  });
  form.addEventListener("submit", () => {
    dirty = false;
  });
  window.addEventListener("beforeunload", (event) => {
    if (!dirty) return;
    event.preventDefault();
    event.returnValue = "";
  });

  const deadline = new Date(timer.dataset.deadline).getTime();
  const tick = () => {
    const remaining = Math.max(0, deadline - Date.now());
    const minutes = Math.floor(remaining / 60000);
    const seconds = Math.floor((remaining % 60000) / 1000);
    timer.textContent = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
    if (remaining <= 0) {
      dirty = false;
      form.submit();
      return;
    }
    window.setTimeout(tick, 1000);
  };
  tick();
})();
