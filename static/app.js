// 採点基準・詳細トグル（全ページ共通）
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.criteria-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = document.getElementById(btn.dataset.target);
      if (!target) return;
      target.classList.toggle('d-none');
      const isHidden = target.classList.contains('d-none');
      // テキストに ▾/▴ が含まれる場合だけ置換
      if (btn.textContent.includes('▾') || btn.textContent.includes('▴')) {
        btn.textContent = btn.textContent
          .replace('▾', isHidden ? '▾' : '▴')
          .replace('▴', isHidden ? '▾' : '▴');
      }
    });
  });
});

// 日付入力から曜日を自動設定
document.addEventListener('DOMContentLoaded', () => {
  const dateInput = document.querySelector('input[name="session_date"]');
  const daySelect = document.querySelector('select[name="day_of_week"]');
  if (!dateInput || !daySelect) return;

  const DAYS = ['日', '月', '火', '水', '木', '金', '土'];
  dateInput.addEventListener('change', () => {
    const d = new Date(dateInput.value);
    if (!isNaN(d)) {
      daySelect.value = DAYS[d.getDay()];
    }
  });
});
