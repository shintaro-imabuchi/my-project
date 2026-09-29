// 開催情報一覧のクライアントサイド絞り込み。
// HTMLには常に全イベントが出力されており（クロール対策）、
// チェックボックスの選択状態に応じてdisplayを切り替えるだけ。
(function () {
  const typeCheckboxes = document.querySelectorAll(".filter-event-type");
  const statusCheckboxes = document.querySelectorAll(".filter-status");
  const cards = document.querySelectorAll(".event-card");
  const noMatch = document.getElementById("no-match");

  function checkedValues(checkboxes) {
    return Array.from(checkboxes)
      .filter((cb) => cb.checked)
      .map((cb) => cb.value);
  }

  function applyFilter() {
    const checkedTypes = checkedValues(typeCheckboxes);
    const checkedStatuses = checkedValues(statusCheckboxes);
    let visibleCount = 0;

    cards.forEach((card) => {
      const matches =
        checkedTypes.includes(card.dataset.eventType) &&
        checkedStatuses.includes(card.dataset.statusLabel);
      card.hidden = !matches;
      if (matches) visibleCount += 1;
    });

    noMatch.hidden = visibleCount > 0;
  }

  typeCheckboxes.forEach((cb) => cb.addEventListener("change", applyFilter));
  statusCheckboxes.forEach((cb) => cb.addEventListener("change", applyFilter));
  applyFilter();
})();
