const form = document.querySelector("#question-form");
const questionInput = document.querySelector("#question-input");
const askButton = document.querySelector("#ask-button");
const resultsBody = document.querySelector("#results-body");
const statusMessage = document.querySelector("#request-status");
const resultCount = document.querySelector("#result-count");
const connectionLabel = document.querySelector("#connection-label");
const followUpWords = ["this", "that", "same", "split", "also", "now", "instead", "compare", "again"];

let latestSql = null;

function appendText(parent, tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  element.textContent = text;
  parent.append(element);
  return element;
}

function addCell(row, className) {
  const cell = document.createElement("td");
  if (className) cell.className = className;
  row.append(cell);
  return cell;
}

function addQuestionCell(row, item) {
  const cell = addCell(row, "question-cell");
  appendText(cell, "span", "cell-eyebrow", "YOUR QUESTION");
  appendText(cell, "p", "question-copy", item.question);
}

function addQueryCell(row, item) {
  const cell = addCell(row, "query-cell");
  appendText(cell, "span", "cell-eyebrow", "GENERATED SQL");
  if (item.sql) {
    const code = document.createElement("code");
    code.className = "sql-code";
    code.textContent = item.sql;
    cell.append(code);
  } else {
    appendText(cell, "span", "muted-copy", "No query was generated.");
  }
}

function addOutputCell(row, item) {
  const cell = addCell(row, "output-cell");
  appendText(cell, "span", "cell-eyebrow", "ANSWER");
  if (item.narrative) appendText(cell, "p", "narrative", item.narrative);
  if (item.message) appendText(cell, "p", "response-message", item.message);

  if (item.chart_url) {
    const image = document.createElement("img");
    image.className = "result-chart";
    image.src = item.chart_url;
    image.alt = `Chart for: ${item.question}`;
    image.loading = "lazy";
    cell.append(image);
  }

  if (item.rows.length && item.columns.length) {
    const tableWrap = document.createElement("div");
    tableWrap.className = "data-table-wrap";
    const table = document.createElement("table");
    table.className = "data-table";
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    item.columns.forEach((column) => appendText(headRow, "th", "", column));
    head.append(headRow);
    table.append(head);

    const body = document.createElement("tbody");
    item.rows.slice(0, 50).forEach((values) => {
      const dataRow = document.createElement("tr");
      item.columns.forEach((column) => {
        const value = values[column];
        appendText(dataRow, "td", "", value === null || value === undefined ? "—" : String(value));
      });
      body.append(dataRow);
    });
    table.append(body);
    tableWrap.append(table);
    cell.append(tableWrap);
    if (item.rows.length > 50) {
      appendText(cell, "span", "muted-copy", `Showing first 50 of ${item.rows.length} rows.`);
    }
  } else if (!item.message && !item.narrative) {
    appendText(cell, "span", "muted-copy", "No rows returned.");
  }
}

function addMetricsCell(row, item) {
  const cell = addCell(row, "metrics-cell");
  appendText(cell, "span", "cell-eyebrow", "QUERY METRICS");
  const metrics = document.createElement("dl");
  metrics.className = "metric-list";
  [
    ["Status", item.status],
    ["Rows", String(item.metrics.row_count)],
    ["Columns", String(item.metrics.column_count)],
    ["Time", `${item.metrics.duration_ms} ms`],
  ].forEach(([label, value]) => {
    const entry = document.createElement("div");
    entry.className = "metric-item";
    appendText(entry, "dt", "", label);
    appendText(entry, "dd", label === "Status" ? `status-${value}` : "", value);
    metrics.append(entry);
  });
  cell.append(metrics);
}

function renderResult(item) {
  const row = document.createElement("tr");
  row.className = "result-row";
  addQuestionCell(row, item);
  addQueryCell(row, item);
  addOutputCell(row, item);
  addMetricsCell(row, item);
  resultsBody.replaceChildren(row);
  resultCount.textContent = "Latest answer";
}

function clearPreviousResult() {
  resultsBody.replaceChildren();
  resultCount.textContent = "Loading…";
}

function isFollowUp(question) {
  const words = question.toLowerCase().split(/\W+/);
  return followUpWords.some((word) => words.includes(word));
}

async function checkConnection() {
  try {
    const response = await fetch("/api/status");
    if (!response.ok) throw new Error("Server unavailable");
    const data = await response.json();
    connectionLabel.textContent = data.offline_mode ? "Offline demo mode" : "Connected";
  } catch {
    connectionLabel.textContent = "Disconnected";
    document.querySelector(".connection").classList.add("connection-error");
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) {
    questionInput.focus();
    return;
  }

  askButton.disabled = true;
  askButton.textContent = "Thinking…";
  clearPreviousResult();
  statusMessage.textContent = "Working on your answer…";
  statusMessage.className = "request-status is-visible";

  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        previous_sql: latestSql && isFollowUp(question) ? latestSql : null,
      }),
    });
    const item = await response.json();
    if (!response.ok) throw new Error(item.error || "The question could not be processed.");

    renderResult(item);
    if (item.status === "ok" && item.sql) latestSql = item.sql;
    statusMessage.textContent = item.status === "ok" ? "Answer ready." : `Request ${item.status}.`;
    statusMessage.className = `request-status is-visible status-text-${item.status}`;
    questionInput.value = "";
  } catch (error) {
    statusMessage.textContent = error.message;
    statusMessage.className = "request-status is-visible status-text-error";
    resultCount.textContent = "No answer";
  } finally {
    askButton.disabled = false;
    askButton.replaceChildren();
    const icon = document.createElement("span");
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = "↗";
    askButton.append(icon, document.createTextNode(" Ask AskData"));
  }
});

document.querySelectorAll(".suggestion").forEach((button) => {
  button.addEventListener("click", () => {
    questionInput.value = button.textContent.trim();
    questionInput.focus();
  });
});

checkConnection();
