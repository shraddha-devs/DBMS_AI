(() => {
  "use strict";

  const form = document.getElementById("chat-form");
  const input = document.getElementById("question-input");
  const sendButton = document.getElementById("send-button");
  const messages = document.getElementById("message-list");
  const welcome = document.getElementById("welcome");
  const historyList = document.getElementById("history-list");
  const statusLabel = document.getElementById("connection-label");
  const statusDetail = document.getElementById("connection-detail");
  const statusDot = document.getElementById("connection-dot");
  const dialog = document.getElementById("info-dialog");
  let busy = false;

  const moneyColumns = new Set([
    "SALARY", "SAL", "COMMISSION", "CURRENT_SALARY", "PROPOSED_SALARY",
    "OLD_SALARY", "NEW_SALARY", "SALARY_DIFFERENCE", "TOTAL_SALARY",
    "MAX_SALARY", "MIN_SALARY", "AVG_SALARY",
  ]);

  function formatMoney(value) {
    if (value === null || value === undefined) return "—";
    const number = Number(value);
    if (!Number.isFinite(number)) return String(value);
    return `₹${new Intl.NumberFormat("en-IN", {
      maximumFractionDigits: 2,
    }).format(number)}`;
  }

  function make(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function hideWelcome() {
    welcome.classList.add("is-hidden");
    document.getElementById("composer-hint").classList.add("is-hidden");
  }

  function appendUser(question) {
    hideWelcome();
    const row = make("div", "message-row user-row");
    const bubble = make("div", "user-bubble", question);
    row.append(bubble, make("div", "avatar user-avatar", "YOU"));
    messages.append(row);
    scrollConversation();
  }

  function appendLoading() {
    const row = make("div", "message-row assistant-row loading-row");
    const avatar = make("div", "avatar assistant-avatar", "✦");
    const bubble = make("div", "assistant-bubble loading-bubble");
    bubble.append(make("span", "loading-copy", "Checking the database"));
    const dots = make("span", "loading-dots");
    dots.append(make("i"), make("i"), make("i"));
    bubble.append(dots);
    row.append(avatar, bubble);
    messages.append(row);
    scrollConversation();
    return row;
  }

  function appendTable(container, columns, rows) {
    if (!Array.isArray(columns) || columns.length === 0 || !rows?.length) return;
    const wrapper = make("div", "result-table-wrap");
    const table = make("table", "result-table");
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    for (const column of columns) headRow.append(make("th", "", column.replaceAll("_", " ")));
    head.append(headRow);
    const body = document.createElement("tbody");
    for (const row of rows) {
      const tr = document.createElement("tr");
      for (const column of columns) {
        const cell = make("td");
        const value = row[column];
        cell.textContent = moneyColumns.has(column.toUpperCase())
          ? formatMoney(value)
          : value === null || value === undefined ? "—" : String(value);
        tr.append(cell);
      }
      body.append(tr);
    }
    table.append(head, body);
    wrapper.append(table);
    container.append(wrapper);
  }

  function appendAnswer(data) {
    const row = make("div", "message-row assistant-row");
    row.append(make("div", "avatar assistant-avatar", "✦"));
    const bubble = make("article", "assistant-bubble");
    const meta = make("div", "answer-meta");
    meta.append(
      make("span", "assistant-name", "Database Assistant"),
      make("span", "answer-practical", data.practical || "Database guide"),
    );
    bubble.append(meta, make("p", "answer-text", data.answer || "No answer was returned."));

    if (Number.isInteger(data.result_count)) {
      const count = data.result_count;
      const label = count === 1 ? "1 result" : `${count} results`;
      bubble.append(make("div", "result-count", `${label} · from your database`));
    }
    appendTable(bubble, data.columns, data.rows);

    if (data.query) {
      const details = document.createElement("details");
      details.className = "sql-details";
      const summary = make("summary", "", "View SQL query");
      const code = make("pre", "sql-code");
      code.textContent = data.query;
      details.append(summary, code);
      bubble.append(details);
    }
    if (data.clarification) bubble.classList.add("clarification-bubble");
    row.append(bubble);
    messages.append(row);
    scrollConversation();
  }

  function appendError(message) {
    appendAnswer({
      practical: "Unable to answer",
      answer: message,
      success: false,
    });
  }

  function scrollConversation() {
    const area = document.getElementById("conversation");
    requestAnimationFrame(() => { area.scrollTop = area.scrollHeight; });
  }

  function renderHistory(items) {
    historyList.replaceChildren();
    if (!items?.length) {
      historyList.append(make("p", "empty-history", "Your questions will appear here."));
      return;
    }
    for (const item of [...items].reverse()) {
      const button = make("button", "history-item", item.question);
      button.title = item.question;
      button.addEventListener("click", () => submitQuestion(item.question));
      historyList.append(button);
    }
  }

  async function loadHistory() {
    try {
      const response = await fetch("/api/history");
      const data = await response.json();
      if (response.ok) renderHistory(data.messages);
    } catch {
      renderHistory([]);
    }
  }

  async function loadStatus() {
    try {
      const response = await fetch("/api/database-status");
      const data = await response.json();
      statusLabel.textContent = data.connected ? "Database connected" : "Database unavailable";
      statusDetail.textContent = data.connected
        ? `${data.table_count} tables · read-only`
        : "Check the local database file";
      statusDot.classList.toggle("offline", !data.connected);
      statusDetail.title = data.database || "";
    } catch {
      statusLabel.textContent = "Connection unavailable";
      statusDetail.textContent = "The local service could not be reached";
      statusDot.classList.add("offline");
    }
  }

  async function loadSuggestions() {
    try {
      const response = await fetch("/api/suggestions");
      const data = await response.json();
      const extra = document.getElementById("extra-suggestions");
      extra.replaceChildren();
      for (const group of data.groups || []) {
        if (!group.practical.startsWith("Practical")) continue;
        const section = make("div", "suggestion-group");
        section.append(make("div", "suggestion-group-title", group.practical));
        const line = make("div", "suggestion-pills");
        for (const question of group.questions) {
          const button = make("button", "suggestion-pill", question);
          button.addEventListener("click", () => submitQuestion(question));
          line.append(button);
        }
        section.append(line);
        extra.append(section);
      }
    } catch {
      // The six primary suggestions remain available without this enhancement.
    }
  }

  async function submitQuestion(rawQuestion) {
    const question = String(rawQuestion || "").trim();
    if (!question || busy) return;
    input.value = "";
    resizeInput();
    appendUser(question);
    busy = true;
    sendButton.disabled = true;
    sendButton.classList.add("is-loading");
    const loading = appendLoading();
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await response.json();
      loading.remove();
      if (!response.ok && !data.error) {
        appendError("The request could not be completed. Please try again.");
      } else if (data.error) {
        appendError(data.error);
      } else {
        appendAnswer(data);
        await loadHistory();
      }
    } catch {
      loading.remove();
      appendError("Couldn't reach the local assistant. Check that the Flask app is running.");
    } finally {
      busy = false;
      sendButton.classList.remove("is-loading");
      sendButton.disabled = !input.value.trim();
      input.focus();
    }
  }

  function resizeInput() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
    sendButton.disabled = busy || !input.value.trim();
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    submitQuestion(input.value);
  });
  input.addEventListener("input", resizeInput);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitQuestion(input.value);
    }
  });
  document.querySelectorAll(".suggestion-card").forEach((button) => {
    button.addEventListener("click", () => submitQuestion(button.dataset.question));
  });

  async function clearConversation() {
    try {
      await fetch("/api/history", { method: "DELETE" });
      messages.replaceChildren();
      welcome.classList.remove("is-hidden");
      document.getElementById("composer-hint").classList.remove("is-hidden");
      renderHistory([]);
      input.focus();
    } catch {
      appendError("The conversation could not be cleared. Please retry.");
    }
  }
  document.getElementById("new-chat-button").addEventListener("click", clearConversation);
  document.getElementById("clear-conversation").addEventListener("click", clearConversation);
  document.getElementById("clear-history").addEventListener("click", clearConversation);

  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("mobile-backdrop");
  function closeSidebar() {
    sidebar.classList.remove("sidebar-open");
    backdrop.classList.remove("backdrop-visible");
  }
  document.getElementById("menu-button").addEventListener("click", () => {
    sidebar.classList.add("sidebar-open");
    backdrop.classList.add("backdrop-visible");
  });
  document.getElementById("close-sidebar").addEventListener("click", closeSidebar);
  backdrop.addEventListener("click", closeSidebar);

  const panels = {
    overview: {
      title: "Database overview",
      copy: "This assistant reads your existing practicals.db file using SQLite read-only mode. No chat question can change practical data.",
    },
    practicals: {
      title: "Five supported practicals",
      copy: "Practical 1: transactions and constraints. Practical 2: employee ALTER, UPDATE, rename and delete. Practical 3: company queries. Practical 4: customer trigger audit. Practical 5: Python sqlite3 cursor.",
    },
    about: {
      title: "About this project",
      copy: "A local Flask and SQLite natural-language assistant. It uses validated query templates and lightweight intent recognition; no external AI API or database credentials are required.",
    },
  };
  document.querySelectorAll("[data-panel]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-panel]").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      const panel = panels[button.dataset.panel];
      document.getElementById("dialog-content").replaceChildren(
        make("h2", "", panel.title),
        make("p", "", panel.copy),
      );
      dialog.showModal();
      closeSidebar();
    });
  });
  document.getElementById("close-dialog").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });

  loadStatus();
  loadSuggestions();
  loadHistory();
})();
