const taskConfig = {
  qa: { heading: "Ask EduGenie", label: "Your question", placeholder: "Enter your question here...", button: "Ask EduGenie", title: "Answer", hint: "Ask about any academic topic." },
  explain: { heading: "Explain a Topic", label: "Topic to explain", placeholder: "Enter a topic to explain...", button: "Explain Topic", title: "Explanation", hint: "Turn a difficult concept into a clear explanation." },
  summarize: { heading: "Summarize Content", label: "Text to summarize", placeholder: "Paste a lesson, article, or study notes...", button: "Summarize", title: "Summary", hint: "Condense long material into the key points." },
  quiz: { heading: "Generate a Quiz", label: "Quiz topic or passage", placeholder: "Enter a topic or paste source material...", button: "Generate Quiz", title: "Quiz", hint: "Create three multiple-choice questions." },
  recommendations: { heading: "Build a Learning Path", label: "Learning goal", placeholder: "Describe what you want to learn...", button: "Build Learning Path", title: "Learning path", hint: "Get a practical path from beginner to advanced." }
};

const endpoints = { qa: "/qa", explain: "/explain", summarize: "/summarize", quiz: "/quiz", recommendations: "/learn/recommendations" };
const apiBase = (window.EDUGENIE_CONFIG?.apiBaseUrl || "http://127.0.0.1:8001").replace(/\/$/, "");

const form = document.querySelector("#learning-form");
const task = document.querySelector("#task");
const formTitle = document.querySelector("#form-title");
const input = document.querySelector("#user-input");
const inputLabel = document.querySelector("#input-label");
const hint = document.querySelector("#hint");
const characterCount = document.querySelector("#character-count");
const button = document.querySelector("#submit-button");
const result = document.querySelector("#result");
const emptyState = document.querySelector("#empty-state");
const resultContent = document.querySelector("#result-content");
const resultTitle = document.querySelector("#result-title");
const modelBadge = document.querySelector("#model-badge");
const copyButton = document.querySelector("#copy-button");
const answer = document.querySelector("#answer");
const apiStatus = document.querySelector("#api-status");

function setApiStatus(online) {
  apiStatus.classList.toggle("offline", !online);
  apiStatus.lastElementChild.textContent = online ? "Online" : "API offline";
}

async function checkApiStatus() {
  try {
    const response = await fetch(`${apiBase}/health`, { signal: AbortSignal.timeout(5000) });
    setApiStatus(response.ok);
  } catch {
    setApiStatus(false);
  }
}

function updateMode() {
  const config = taskConfig[task.value];
  formTitle.textContent = config.heading;
  inputLabel.textContent = config.label;
  input.placeholder = config.placeholder;
  button.innerHTML = `<span>${config.button}</span><span aria-hidden="true">→</span>`;
  hint.textContent = config.hint;
}

function updateCharacterCount() {
  characterCount.textContent = `${input.value.length.toLocaleString()} / 20,000`;
}

task.addEventListener("change", updateMode);
input.addEventListener("input", updateCharacterCount);
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

copyButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(answer.textContent);
    copyButton.textContent = "Copied";
  } catch {
    copyButton.textContent = "Copy failed";
  }
  window.setTimeout(() => { copyButton.textContent = "Copy"; }, 1400);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const value = input.value.trim();
  if (!value) { input.focus(); return; }

  const config = taskConfig[task.value];
  button.disabled = true;
  button.innerHTML = '<span>Working...</span><span class="loading" aria-hidden="true"></span>';
  result.setAttribute("aria-busy", "true");
  emptyState.hidden = true;
  resultContent.hidden = false;
  resultTitle.textContent = config.title;
  modelBadge.textContent = "Generating";
  copyButton.hidden = true;
  answer.className = "";
  answer.textContent = "EduGenie is preparing your response...";

  try {
    const response = await fetch(apiBase + endpoints[task.value], {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input: value })
    });
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : null;
    if (!response.ok) throw new Error(data?.detail || "The request could not be completed.");
    if (!data?.result || !data?.model) throw new Error("The API returned an invalid response.");
    setApiStatus(true);
    modelBadge.textContent = data.model;
    answer.textContent = data.result;
    copyButton.hidden = false;
  } catch (error) {
    if (error instanceof TypeError) setApiStatus(false);
    modelBadge.textContent = "Request failed";
    answer.className = "error";
    answer.textContent = error instanceof TypeError ? "Cannot connect to EduGenie. Start FastAPI on port 8001." : error.message;
  } finally {
    button.disabled = false;
    button.innerHTML = `<span>${config.button}</span><span aria-hidden="true">→</span>`;
    result.setAttribute("aria-busy", "false");
  }
});

updateMode();
updateCharacterCount();
checkApiStatus();
