const { invoke } = window.__TAURI__.core;

const logEl = document.getElementById("log");
const formEl = document.getElementById("prompt-form");
const inputEl = document.getElementById("prompt-input");
const resetBtn = document.getElementById("reset-btn");
const plotEl = document.getElementById("plot");

const keyModal = document.getElementById("key-modal");
const keyInput = document.getElementById("key-input");
const keySubmit = document.getElementById("key-submit");
const keyError = document.getElementById("key-error");

function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = text;
  logEl.appendChild(div);
  logEl.scrollTop = logEl.scrollHeight;
  return div;
}

function setBusy(busy) {
  inputEl.disabled = busy;
  formEl.querySelector("button").disabled = busy;
}

function linspace(min, max, n) {
  const out = new Array(n);
  const step = (max - min) / (n - 1);
  for (let i = 0; i < n; i++) out[i] = min + step * i;
  return out;
}

function safeEval(expr, scope) {
  try {
    const v = math.evaluate(expr, scope);
    return typeof v === "number" && Number.isFinite(v) ? v : NaN;
  } catch {
    return NaN;
  }
}

function renderPlot(spec) {
  const vars = spec.variables || ["x"];
  const domain = spec.domain || {};
  const xMin = domain.xMin ?? -10;
  const xMax = domain.xMax ?? 10;

  if (spec.kind === "3d") {
    const yMin = domain.yMin ?? xMin;
    const yMax = domain.yMax ?? xMax;
    const steps = 80;
    const xs = linspace(xMin, xMax, steps);
    const ys = linspace(yMin, yMax, steps);
    const trace = spec.traces?.[0] ?? { expr: "0" };
    const zs = ys.map((yv) =>
      xs.map((xv) => safeEval(trace.expr, { [vars[0] || "x"]: xv, [vars[1] || "y"]: yv }))
    );

    Plotly.newPlot(
      plotEl,
      [
        {
          type: "surface",
          x: xs,
          y: ys,
          z: zs,
          colorscale: "Viridis",
          showscale: false,
        },
      ],
      {
        title: spec.title || trace.expr,
        autosize: true,
        margin: { l: 0, r: 0, b: 0, t: 40 },
        scene: { xaxis: { title: vars[0] || "x" }, yaxis: { title: vars[1] || "y" }, zaxis: { title: "z" } },
      },
      { responsive: true }
    );
  } else {
    const steps = 800;
    const xs = linspace(xMin, xMax, steps);
    const traces = (spec.traces || []).map((t) => ({
      type: "scatter",
      mode: "lines",
      name: t.label || t.expr,
      x: xs,
      y: xs.map((xv) => safeEval(t.expr, { [vars[0] || "x"]: xv })),
    }));

    Plotly.newPlot(
      plotEl,
      traces,
      {
        title: spec.title || traces.map((t) => t.name).join(", "),
        autosize: true,
        margin: { l: 50, r: 20, b: 40, t: 40 },
        xaxis: { title: vars[0] || "x" },
        yaxis: { title: "y", scaleanchor: "x", scaleratio: 1 },
      },
      { responsive: true }
    );
  }
}

async function ensureApiKey() {
  const hasKey = await invoke("has_api_key");
  if (!hasKey) {
    keyModal.classList.remove("hidden");
  }
}

keySubmit.addEventListener("click", async () => {
  const key = keyInput.value.trim();
  if (!key) return;
  try {
    await invoke("set_api_key", { key });
    keyModal.classList.add("hidden");
    keyError.classList.add("hidden");
  } catch (e) {
    keyError.textContent = String(e);
    keyError.classList.remove("hidden");
  }
});

formEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const prompt = inputEl.value.trim();
  if (!prompt) return;
  addMessage("user", prompt);
  inputEl.value = "";
  setBusy(true);
  const thinking = addMessage("assistant", "…");
  try {
    const result = await invoke("ask_claude", { prompt });
    thinking.remove();
    if (result.type === "plot") {
      addMessage("assistant", `Plotted: ${result.data.title || result.data.traces?.map((t) => t.expr).join(", ")}`);
      renderPlot(result.data);
    } else {
      addMessage("assistant", result.data);
    }
  } catch (err) {
    thinking.remove();
    addMessage("error", String(err));
  } finally {
    setBusy(false);
    inputEl.focus();
  }
});

resetBtn.addEventListener("click", async () => {
  await invoke("reset_conversation");
  logEl.innerHTML = "";
  plotEl.innerHTML = "";
});

ensureApiKey();
