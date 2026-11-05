"use strict";
const $ = (selector) => document.querySelector(selector);
let currentUser = null;
const statusNames = {new: "Новая", work: "В работе", done: "Решена"};
const priorityNames = {low: "Низкий", normal: "Обычный", high: "Высокий"};
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: {"Content-Type": "application/json", "X-CSRF-Token": currentUser?.csrf || "", ...options.headers} });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Ошибка ${response.status}`);
  return data;
}
function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function enter(user) {
  currentUser = user;
  $("#login-panel").hidden = true;
  $("#workspace").hidden = false;
  $("#account").hidden = false;
  $("#username").textContent = user.username;
  $("#role-label").textContent = user.role === "admin" ? "Кабинет сотрудника поддержки" : "Личный кабинет";
  return refresh();
}
async function refresh() {
  try {
    const rows = await api(`/api/tickets?status=${encodeURIComponent($("#status-filter").value)}`);
    $("#tickets").replaceChildren();
    $("#summary").textContent = `Найдено заявок: ${rows.length}`;
    $("#empty").hidden = rows.length > 0;
    for (const ticket of rows) {
      const tr = node("tr");
      tr.append(node("td", `#${ticket.id}`));
      const title = node("td");
      title.append(node("span", ticket.title, "ticket-title"));
      title.append(node("span", `${ticket.owner} · ${new Date(ticket.created_at).toLocaleDateString("ru-RU")}`, "meta"));
      tr.append(title, node("td", priorityNames[ticket.priority], `priority-${ticket.priority}`));
      const status = node("td"); status.append(node("span", statusNames[ticket.status], `badge ${ticket.status}`)); tr.append(status);
      const actions = node("td");
      const view = node("button", "Открыть");
      view.addEventListener("click", () => {
        $("#detail-title").textContent = `Заявка #${ticket.id}`;
        $("#detail-body").textContent = `${ticket.title}\n\n${ticket.description}`;
        $("#detail-meta").textContent = `Статус: ${statusNames[ticket.status]}. Автор: ${ticket.owner}.`;
        $("#detail-dialog").showModal();
      });
      actions.append(view);
      if (currentUser.role === "admin") {
        const select = node("select"); select.setAttribute("aria-label", `Статус заявки ${ticket.id}`);
        select.append(new Option("Изменить статус", ""));
        const allowed = {new: ["work"], work: ["new", "done"], done: ["work"]};
        allowed[ticket.status].forEach(value => select.append(new Option(statusNames[value], value)));
        select.addEventListener("change", async () => {
          if (!select.value) return;
          try {
            await api(`/api/tickets/${ticket.id}`, {method: "PATCH", body: JSON.stringify({status: select.value})});
            $("#notice").textContent = `Статус заявки #${ticket.id} обновлён`;
            await refresh();
          } catch (error) { $("#app-error").textContent = error.message; }
        });
        actions.append(select);
      }
      tr.append(actions); $("#tickets").append(tr);
    }
  } catch (error) { $("#app-error").textContent = error.message; }
}
$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault(); $("#login-error").textContent = "";
  const button = event.target.querySelector("button[type=submit]"); button.disabled = true;
  try { await enter(await api("/api/login", {method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(event.target)))})); }
  catch (error) { $("#login-error").textContent = error.message; }
  finally { button.disabled = false; }
});
$("#logout").addEventListener("click", async () => {
  try { await api("/api/logout", {method: "POST", body: "{}"}); location.reload(); }
  catch (error) { $("#app-error").textContent = error.message; }
});
$("#new-ticket").addEventListener("click", () => { $("#create-error").textContent = ""; $("#create-dialog").showModal(); });
document.querySelectorAll(".close-dialog").forEach(button => button.addEventListener("click", () => button.closest("dialog").close()));
$("#ticket-form").addEventListener("submit", async (event) => {
  event.preventDefault(); const button = event.target.querySelector("button[type=submit]"); button.disabled = true;
  try {
    const ticket = await api("/api/tickets", {method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(event.target)))});
    event.target.reset(); $("#create-dialog").close(); $("#notice").textContent = `Заявка #${ticket.id} создана`;
    $("#status-filter").value = ""; await refresh();
  } catch (error) { $("#create-error").textContent = error.message; }
  finally { button.disabled = false; }
});
$("#status-filter").addEventListener("change", () => { $("#app-error").textContent = ""; refresh(); });
$("#export").addEventListener("click", () => { location.href = `/api/export?status=${encodeURIComponent($("#status-filter").value)}`; });
api("/api/me").then(user => { if (user.id) return enter(user); }).catch(() => {});
