import { linspace, safeEval } from "./plot-math.js";
import { canCombine, combineSpecs } from "./combine.js";

const { invoke } = window.__TAURI__.core;

const logEl = document.getElementById("log");
const formEl = document.getElementById("prompt-form");
const inputEl = document.getElementById("prompt-input");
const resetBtn = document.getElementById("reset-btn");
const plotEl = document.getElementById("plot");
const addFunctionBtn = document.getElementById("add-function-btn");

const keyModal = document.getElementById("key-modal");
const keyInput = document.getElementById("key-input");
const keySubmit = document.getElementById("key-submit");
const keyError = document.getElementById("key-error");

const plotTitleEl = document.getElementById("plot-title");
const plotSubtitleEl = document.getElementById("plot-subtitle");
const descriptionToggleBtn = document.getElementById("description-toggle");
const plotDescriptionEl = document.getElementById("plot-description");
const topicBarEl = document.getElementById("topic-bar");
const topicLabelEl = document.getElementById("topic-label");
const topicInputEl = document.getElementById("topic-input");
const saveToLibraryBtn = document.getElementById("save-to-library-btn");

const libraryToggleBtn = document.getElementById("library-toggle");
const libraryListEl = document.getElementById("library-list");

const DEFAULT_PROMPT_PLACEHOLDER = inputEl.placeholder;

let currentSpec = null;
let addingFunction = false;

function setAddingFunction(on) {
  addingFunction = on;
  addFunctionBtn.classList.toggle("active", on);
  inputEl.placeholder = on ? "Describe the function to add to this plot…" : DEFAULT_PROMPT_PLACEHOLDER;
}

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

const SURFACE_COLORS = ["#4e79a7", "#f28e2b", "#e15759", "#59a14f", "#b07aa1", "#76b7b2"];

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
    const traces = spec.traces?.length ? spec.traces : [{ expr: "0" }];
    const surfaces = traces.map((trace, i) => {
      const color = SURFACE_COLORS[i % SURFACE_COLORS.length];
      return {
        type: "surface",
        name: trace.label || trace.expr,
        x: xs,
        y: ys,
        z: ys.map((yv) =>
          xs.map((xv) => safeEval(trace.expr, { [vars[0] || "x"]: xv, [vars[1] || "y"]: yv }))
        ),
        colorscale: [[0, color], [1, color]],
        showscale: false,
      };
    });

    Plotly.newPlot(
      plotEl,
      surfaces,
      {
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
        autosize: true,
        margin: { l: 50, r: 20, b: 40, t: 40 },
        xaxis: { title: vars[0] || "x" },
        yaxis: { title: "y", scaleanchor: "x", scaleratio: 1 },
      },
      { responsive: true }
    );
  }
}

function renderMeta(spec) {
  plotTitleEl.textContent = spec.title || "";

  plotSubtitleEl.innerHTML = "";
  if (spec.subtitle) {
    try {
      katex.render(spec.subtitle, plotSubtitleEl, { throwOnError: false });
    } catch {
      plotSubtitleEl.textContent = spec.subtitle;
    }
  }

  plotDescriptionEl.classList.add("hidden");
  plotDescriptionEl.innerHTML = "";
  if (spec.description) {
    descriptionToggleBtn.classList.remove("hidden");
    descriptionToggleBtn.textContent = "Description ▸";
    descriptionToggleBtn.dataset.rendered = "false";
  } else {
    descriptionToggleBtn.classList.add("hidden");
  }

  addFunctionBtn.classList.remove("hidden");

  const combined = spec.combined === true;
  topicBarEl.classList.remove("hidden");
  topicLabelEl.classList.toggle("hidden", combined);
  topicInputEl.classList.toggle("hidden", combined);
  topicInputEl.value = spec.suggested_topic || "";
}

addFunctionBtn.addEventListener("click", () => {
  setAddingFunction(!addingFunction);
  if (addingFunction) inputEl.focus();
});

descriptionToggleBtn.addEventListener("click", () => {
  const isHidden = plotDescriptionEl.classList.contains("hidden");
  if (isHidden) {
    if (descriptionToggleBtn.dataset.rendered !== "true" && currentSpec) {
      plotDescriptionEl.textContent = currentSpec.description || "";
      try {
        renderMathInElement(plotDescriptionEl, {
          delimiters: [
            { left: "$$", right: "$$", display: true },
            { left: "\\(", right: "\\)", display: false },
            { left: "$", right: "$", display: false },
          ],
          throwOnError: false,
        });
      } catch {
        // leave plain text if auto-render fails
      }
      descriptionToggleBtn.dataset.rendered = "true";
    }
    plotDescriptionEl.classList.remove("hidden");
    descriptionToggleBtn.textContent = "Description ▾";
  } else {
    plotDescriptionEl.classList.add("hidden");
    descriptionToggleBtn.textContent = "Description ▸";
  }
});

saveToLibraryBtn.addEventListener("click", async () => {
  if (!currentSpec) return;
  const combined = currentSpec.combined === true;
  const topic = topicInputEl.value.trim();
  if (!topic && !combined) return;
  saveToLibraryBtn.disabled = true;
  try {
    const entry = {
      id: "",
      title: currentSpec.title || "",
      subtitle: currentSpec.subtitle || "",
      description: currentSpec.description || "",
      kind: currentSpec.kind || "2d",
      variables: currentSpec.variables || ["x"],
      domain: currentSpec.domain || {},
      traces: currentSpec.traces || [],
      created_at: "",
      combined,
    };
    await invoke("save_function", { topic, entry });
    await loadLibrary();
  } catch (e) {
    addMessage("error", String(e));
  } finally {
    saveToLibraryBtn.disabled = false;
  }
});

function buildLibraryFunction(fn) {
  const item = document.createElement("div");
  item.className = "library-function";

  const titleRow = document.createElement("div");
  titleRow.className = "library-function-title";
  titleRow.textContent = fn.title || "(untitled)";
  titleRow.addEventListener("click", () => {
    currentSpec = fn;
    renderPlot(fn);
    renderMeta(fn);
  });

  const subtitleRow = document.createElement("div");
  subtitleRow.className = "library-function-subtitle";
  if (fn.subtitle) {
    try {
      katex.render(fn.subtitle, subtitleRow, { throwOnError: false });
    } catch {
      subtitleRow.textContent = fn.subtitle;
    }
  }

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "library-function-delete";
  deleteBtn.textContent = "✕";
  deleteBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    if (!confirm(`Delete "${fn.title || fn.id}" from the library?`)) return;
    try {
      await invoke("delete_function", { id: fn.id });
      await loadLibrary();
    } catch (err) {
      addMessage("error", String(err));
    }
  });

  item.appendChild(titleRow);
  item.appendChild(subtitleRow);
  item.appendChild(deleteBtn);
  return item;
}

function buildLibraryGroup(name, functions) {
  const group = document.createElement("div");
  group.className = "library-topic";

  const label = (open) => `${name} (${functions.length}) ${open ? "▾" : "▸"}`;

  const header = document.createElement("button");
  header.type = "button";
  header.className = "library-topic-header";
  header.textContent = label(false);

  const list = document.createElement("div");
  list.className = "library-functions hidden";

  header.addEventListener("click", () => {
    list.classList.toggle("hidden");
    header.textContent = label(!list.classList.contains("hidden"));
  });

  for (const fn of functions) {
    list.appendChild(buildLibraryFunction(fn));
  }

  group.appendChild(header);
  group.appendChild(list);
  return group;
}

function renderLibraryList(topics, combined) {
  libraryListEl.innerHTML = "";
  const hasTopics = Array.isArray(topics) && topics.length > 0;
  const hasCombined = Array.isArray(combined) && combined.length > 0;
  if (!hasTopics && !hasCombined) {
    const empty = document.createElement("p");
    empty.className = "library-empty";
    empty.textContent = "No saved functions yet.";
    libraryListEl.appendChild(empty);
    return;
  }

  if (hasCombined) {
    libraryListEl.appendChild(buildLibraryGroup("Combined", combined));
  }
  for (const topic of topics || []) {
    libraryListEl.appendChild(buildLibraryGroup(topic.name, topic.functions));
  }
}

async function loadLibrary() {
  try {
    const [topics, combined] = await Promise.all([invoke("list_topics"), invoke("list_combined")]);
    renderLibraryList(topics, combined);
  } catch (e) {
    addMessage("error", String(e));
  }
}

libraryToggleBtn.addEventListener("click", () => {
  const isHidden = libraryListEl.classList.contains("hidden");
  libraryListEl.classList.toggle("hidden");
  libraryToggleBtn.textContent = isHidden ? "Library ▾" : "Library ▸";
});

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
  const combining = addingFunction && currentSpec !== null;
  setAddingFunction(false);
  addMessage("user", prompt);
  inputEl.value = "";
  setBusy(true);
  const thinking = addMessage("assistant", "…");
  try {
    const result = await invoke("ask_claude", { prompt });
    thinking.remove();
    if (result.type === "plot" && combining) {
      if (!canCombine(currentSpec, result.data)) {
        addMessage(
          "error",
          result.data.kind === "3d"
            ? "A 3D function can only be added to a 3D plot."
            : "A 2D function can only be added to a 2D plot."
        );
      } else {
        const next = combineSpecs(currentSpec, result.data);
        if (next === currentSpec) {
          addMessage("assistant", "The response did not contain a function to add.");
        } else {
          addMessage("assistant", `Added: ${result.data.title || result.data.traces?.map((t) => t.expr).join(", ")}`);
          currentSpec = next;
          renderPlot(currentSpec);
          renderMeta(currentSpec);
        }
      }
    } else if (result.type === "plot") {
      addMessage("assistant", `Plotted: ${result.data.title || result.data.traces?.map((t) => t.expr).join(", ")}`);
      currentSpec = result.data;
      renderPlot(result.data);
      renderMeta(result.data);
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
  currentSpec = null;
  setAddingFunction(false);
  addFunctionBtn.classList.add("hidden");
  plotTitleEl.textContent = "";
  plotSubtitleEl.innerHTML = "";
  plotDescriptionEl.innerHTML = "";
  plotDescriptionEl.classList.add("hidden");
  descriptionToggleBtn.classList.add("hidden");
  topicBarEl.classList.add("hidden");
});

ensureApiKey();
loadLibrary();
