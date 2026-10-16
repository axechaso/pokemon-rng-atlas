(() => {
  const list = document.getElementById('articleList');
  if (!list) return;
  const search = document.getElementById('articleSearch');
  const sort = document.getElementById('sortOrder');
  const type = document.getElementById('sourceType');
  const count = document.getElementById('resultCount');
  const empty = document.getElementById('noResults');
  const cards = Array.from(list.querySelectorAll('.article-card'));
  const params = new URLSearchParams(location.search);
  if (params.has('q')) search.value = params.get('q');
  if (Array.from(type.options).some(option => option.value === params.get('type'))) {
    type.value = params.get('type');
  }
  function update() {
    const query = search.value.trim().toLocaleLowerCase();
    let visible = 0;
    cards.forEach(card => {
      card.hidden = (query.length > 0 && !card.dataset.search.includes(query)) ||
        (type.value !== 'all' && card.dataset.type !== type.value);
      if (!card.hidden) visible++;
    });
    const filtered = cards.slice().sort((a,b) => {
      if (sort.value === 'title') return a.querySelector('h3').textContent.localeCompare(b.querySelector('h3').textContent,'zh');
      if (!a.dataset.date || !b.dataset.date) return Number(!a.dataset.date) - Number(!b.dataset.date);
      return sort.value === 'oldest' ? a.dataset.date.localeCompare(b.dataset.date) : b.dataset.date.localeCompare(a.dataset.date);
    });
    filtered.forEach(card => list.appendChild(card));
    count.textContent = `${visible} 条`;
    empty.hidden = visible !== 0;
  }
  search.addEventListener('input',update);
  sort.addEventListener('change',update);
  type.addEventListener('change',update);
  update();
})();
