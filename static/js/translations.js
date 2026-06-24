function translateTextNodes(node) {
  if (node.nodeType === 3) {
    let val = node.nodeValue;

    if (val.includes("Logout")) val = val.replace("Logout", "Выход");
    if (/go back/i.test(val)) val = val.replace(/go back/i, "Назад");
    if (val.includes("New ")) val = val.replace("New ", "Добавить ");
    if (val.includes("Actions")) val = val.replace("Actions", "Действия");
    if (val.includes("Delete selected items"))
      val = val.replace("Delete selected items", "Удалить выбранные");
    if (val.includes("Delete")) val = val.replace("Delete", "Удалить");
    if (val.includes("Edit")) val = val.replace("Edit", "Изменить");
    if (val.includes("View")) val = val.replace("View", "Просмотр");
    if (val.includes("Save")) val = val.replace("Save", "Сохранить");
    if (val.includes("Cancel")) val = val.replace("Cancel", "Отмена");
    if (val.includes("Search") && !val.includes("Search:"))
      val = val.replace("Search", "Найти");
    if (val.includes("Search:")) val = val.replace("Search:", "Поиск:");
    if (val.includes("Export")) val = val.replace("Export", "Экспорт");

    if (val !== node.nodeValue) node.nodeValue = val;
  } else if (
    node.nodeType === 1 &&
    node.nodeName !== "SCRIPT" &&
    node.nodeName !== "STYLE"
  ) {
    node.childNodes.forEach(translateTextNodes);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  translateTextNodes(document.body);

  const translateAttr = (selector, attr, newText) => {
    document
      .querySelectorAll(selector)
      .forEach((e) => e.setAttribute(attr, newText));
  };

  translateAttr('[title="View"]', "title", "Просмотр");
  translateAttr(
    '[data-bs-original-title="View"]',
    "data-bs-original-title",
    "Просмотр",
  );

  translateAttr('[title="Edit"]', "title", "Редактировать");
  translateAttr(
    '[data-bs-original-title="Edit"]',
    "data-bs-original-title",
    "Редактировать",
  );

  translateAttr('[title="Delete"]', "title", "Удалить");
  translateAttr(
    '[data-bs-original-title="Delete"]',
    "data-bs-original-title",
    "Удалить",
  );
});
