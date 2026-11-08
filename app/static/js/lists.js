/* Listes : tri par colonne, sélection et actions en masse, ouverture dans un nouvel onglet (3.18), pagination (3.19). */
(function () {
  var csrf = (document.querySelector('meta[name=csrf-token]') || {}).content;
  function cellKey(row, i) {
    var c = row.cells[i], t = c ? c.textContent.trim() : '';
    var d = t.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
    return d ? d[3] + d[2] + d[1] : t;
  }
  document.querySelectorAll('table.grid thead').forEach(function (head) {
    var table = head.parentElement, body = table.tBodies[0];
    if (!body || body.rows.length < 2 || !head.rows.length) return;
    Array.prototype.forEach.call(head.rows[0].cells, function (th, i) {
      if (!th.textContent.trim() || th.colSpan > 1) return;
      th.classList.add('is-sortable'); th.tabIndex = 0; th.title = 'Trier';
      function sort(force) {
        var asc = typeof force === 'boolean' ? force : th.getAttribute('aria-sort') !== 'ascending';
        Array.prototype.forEach.call(head.rows[0].cells, function (o) { o.removeAttribute('aria-sort'); });
        th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');
        var idx = th.cellIndex;
        Array.prototype.slice.call(body.rows).filter(function (r) { return r.cells.length > 1; })
          .sort(function (a, b) { var r = cellKey(a, idx).localeCompare(cellKey(b, idx), 'fr', { numeric: true, sensitivity: 'base' }); return asc ? r : -r; })
          .forEach(function (r) { body.appendChild(r); });
        if (table._pgSorted) table._pgSorted(idx, asc);
      }
      th._sort = sort;
      th.addEventListener('click', sort);
      th.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); sort(); } });
    });
  });
  // Ctrl + clic ou clic molette sur une ligne : nouvel onglet
  function rowUrl(tr) { var m = (tr.getAttribute('onclick') || '').match(/window\.location='([^']+)'/); return m && m[1]; }
  document.addEventListener('click', function (e) {
    var tr = e.target.closest && e.target.closest('tr.row-link');
    if (tr && (e.ctrlKey || e.metaKey) && !e.target.closest('a,button,input,select,label') && rowUrl(tr)) { e.stopPropagation(); e.preventDefault(); window.open(rowUrl(tr), '_blank'); }
  }, true);
  document.addEventListener('auxclick', function (e) {
    var tr = e.button === 1 && e.target.closest && e.target.closest('tr.row-link');
    if (tr && rowUrl(tr)) { e.preventDefault(); window.open(rowUrl(tr), '_blank'); }
  });
  // Sélection et actions en masse
  var bars = {};
  function post(path, ids, extra) {
    var f = document.createElement('form'); f.method = 'post'; f.action = path;
    function add(n, v) { var i = document.createElement('input'); i.type = 'hidden'; i.name = n; i.value = v; f.appendChild(i); }
    add('csrf_token', csrf); add('next', location.pathname + location.search);
    ids.forEach(function (id) { add('ids', id); });
    Object.keys(extra || {}).forEach(function (k) { add(k, extra[k]); });
    document.body.appendChild(f); f.submit(); f.remove();
  }
  function barFor(kind) {
    if (bars[kind]) return bars[kind];
    var b = document.createElement('div'); b.className = 'bulk-bar'; b.hidden = true; b.setAttribute('role', 'region'); b.setAttribute('aria-label', 'Actions sur la sélection');
    b.innerHTML = '<b class="bulk-bar__n"></b><button type="button" class="btn btn--ghost btn--sm bulk-bar__more" hidden></button><select class="bulk-bar__act" aria-label="Action"><option value="">Choisir une action…</option><option value="export">Exporter en CSV</option></select><select class="bulk-bar__val" aria-label="Valeur" hidden></select><button type="button" class="btn btn--primary btn--sm bulk-bar__go" disabled>Appliquer</button><button type="button" class="btn btn--ghost btn--sm bulk-bar__clear">Désélectionner</button>';
    document.body.appendChild(b);
    var act = b.querySelector('.bulk-bar__act'), val = b.querySelector('.bulk-bar__val'), go = b.querySelector('.bulk-bar__go'), cfg = null;
    fetch('/masse/' + kind + '/config', { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (c) {
      cfg = c;
      function opt(v, t) { var o = document.createElement('option'); o.value = v; o.textContent = t; act.appendChild(o); }
      if (c.users.length) opt('owner', 'Attribuer à…');
      if (c.statuses.length) opt('status', 'Changer le statut…');
      if (c.canDelete) opt('delete', 'Supprimer…');
    });
    function refresh() {
      var a = act.value, needs = a === 'owner' || a === 'status';
      val.hidden = !needs;
      if (needs) {
        val.innerHTML = '';
        (a === 'owner' ? cfg.users : cfg.statuses).forEach(function (x) { var o = document.createElement('option'); o.value = x[0]; o.textContent = x[1]; val.appendChild(o); });
      }
      go.disabled = !a;
      go.className = 'btn btn--sm bulk-bar__go ' + (a === 'delete' ? 'btn--danger' : 'btn--primary');
    }
    act.addEventListener('change', refresh);
    go.addEventListener('click', function () {
      var ids = selected(kind), a = act.value, base = '/masse/' + kind + '/';
      if (a === 'export') post(base + 'exporter', ids);
      else if (a === 'owner') post(base + 'attribuer', ids, { user_id: val.value });
      else if (a === 'status') post(base + 'statut', ids, { status: val.value });
      else if (a === 'delete') post(base + 'supprimer', ids);
    });
    b.querySelector('.bulk-bar__more').addEventListener('click', function () { boxes(kind).forEach(function (c) { c.checked = true; }); sync(kind); });
    b.querySelector('.bulk-bar__clear').addEventListener('click', function () { boxes(kind).forEach(function (c) { c.checked = false; }); sync(kind); });
    return (bars[kind] = b);
  }
  function boxes(kind) { return Array.prototype.slice.call(document.querySelectorAll('input.bulk-cb[data-kind="' + kind + '"]')); }
  function selected(kind) { return boxes(kind).filter(function (c) { return c.checked; }).map(function (c) { return c.value; }); }
  function isChecked(c) { return c.checked; }
  function pageBoxes(root) { return Array.prototype.slice.call(root.querySelectorAll('tbody tr:not(.pg-off) input.bulk-cb')); }
  function sync(kind) {
    var n = selected(kind).length, b = barFor(kind), total = boxes(kind).length;
    var vis = boxes(kind).filter(function (c) { return !c.closest('tr.pg-off'); }), off = n - vis.filter(isChecked).length, more = b.querySelector('.bulk-bar__more');
    b.hidden = !n; b.querySelector('.bulk-bar__n').textContent = n + ' sélectionné(s)' + (off ? ', dont ' + off + ' sur d\'autres pages' : '');
    more.hidden = !(n < total && vis.length < total && vis.every(isChecked)); more.textContent = 'Sélectionner les ' + total;
    (document.querySelector('.content') || document.body).style.paddingBottom = b.hidden ? '' : (b.offsetHeight + 28) + 'px';
    document.querySelectorAll('input.bulk-all[data-kind="' + kind + '"]').forEach(function (a) { var t = pageBoxes(a.closest('table')), c = t.filter(isChecked).length; a.checked = c > 0 && c === t.length; a.indeterminate = c > 0 && c < t.length; });
  }
  document.querySelectorAll('table[data-bulk]').forEach(function (table) {
    var kind = table.dataset.bulk, body = table.tBodies[0], rows = Array.prototype.filter.call(body.rows, function (r) { return r.dataset.id; });
    if (!rows.length) return;
    if (table.tHead) { var th = document.createElement('th'); th.className = 'bulk-col'; th.innerHTML = '<input type="checkbox" class="bulk-all" aria-label="Tout sélectionner" data-kind="' + kind + '">'; table.tHead.rows[0].insertBefore(th, table.tHead.rows[0].firstChild); }
    var last = null;
    rows.forEach(function (r) {
      var td = document.createElement('td'); td.className = 'bulk-col';
      var cb = document.createElement('input'); cb.type = 'checkbox'; cb.className = 'bulk-cb'; cb.value = r.dataset.id; cb.dataset.kind = kind; cb.setAttribute('aria-label', 'Sélectionner');
      td.appendChild(cb); r.insertBefore(td, r.firstChild);
      td.addEventListener('click', function (e) {
        e.stopPropagation();
        if (e.target !== cb) { cb.checked = !cb.checked; sync(kind); }
        if (e.shiftKey && last && last !== cb) {            // Maj + clic : toute la plage
          var all = pageBoxes(table), a = all.indexOf(last), b = all.indexOf(cb);      // limitée à la page affichée
          if (a >= 0 && b >= 0) all.slice(Math.min(a, b), Math.max(a, b) + 1).forEach(function (x) { x.checked = cb.checked; });
          sync(kind);
        }
        last = cb;
      });
      cb.addEventListener('change', function () { sync(kind); });
    });
    Array.prototype.forEach.call(body.rows, function (r) { if (!r.dataset.id && r.cells.length === 1) r.cells[0].colSpan += 1; });
    var all = table.querySelector('input.bulk-all');
    if (all) { all.addEventListener('click', function (e) { e.stopPropagation(); }); all.closest('th').addEventListener('click', function (e) { e.stopPropagation(); });
      all.addEventListener('change', function () { pageBoxes(table).forEach(function (c) { c.checked = all.checked; }); sync(kind); }); }
  });
  // Pagination côté navigateur : le tri, la sélection et l'impression portent sur toutes les lignes.
  var SIZES = [25, 50, 100];
  function mem(store, key, value) {
    try {
      if (value === undefined) return JSON.parse(window[store].getItem(key));
      window[store].setItem(key, JSON.stringify(value));
    } catch (e) { return null; }
  }
  function paginate(table, n) {
    var body = table.tBodies[0];
    if (!body || table.hasAttribute('data-nopage') || table.closest('form')) return;    // champs masqués : l'enregistrement serait faussé
    var first = Array.prototype.slice.call(body.rows);
    if (first.length <= SIZES[0]) return;
    if (first.some(function (r) { return r.hidden || r.style.display === 'none' || r.cells.length < 2 || Array.prototype.some.call(r.cells, function (c) { return c.colSpan > 1 || c.rowSpan > 1; }); })) return;   // lignes de regroupement
    var key = 'integra.liste:' + location.pathname + location.search + ':' + n, st = mem('sessionStorage', key) || {}, saved = mem('localStorage', 'integra.lignes');
    var size = SIZES.concat(0).indexOf(saved) >= 0 ? saved : SIZES[0], p = st.p > 0 ? st.p : 1, col = null, dir = true;
    var wrap = table.closest('.table-wrap') || table, nav = document.createElement('nav');
    nav.className = 'pager'; nav.setAttribute('aria-label', 'Pagination du tableau');
    wrap.insertAdjacentElement('afterend', nav);
    function save() { mem('sessionStorage', key, { p: p, c: col, d: dir }); }
    function button(go, label, disabled, current, aria) {
      return '<button type="button" class="pager__btn' + (current ? ' is-on' : '') + '" data-go="' + go + '"' + (disabled ? ' disabled' : '') + (current ? ' aria-current="page"' : '') + (aria ? ' aria-label="' + aria + '"' : '') + '>' + label + '</button>';
    }
    function render(focus) {
      var rows = Array.prototype.slice.call(body.rows), total = rows.length, per = size || total, pages = Math.max(1, Math.ceil(total / per));
      p = Math.min(Math.max(p, 1), pages);
      var from = (p - 1) * per, to = Math.min(from + per, total);
      rows.forEach(function (r, i) { r.classList.toggle('pg-off', i < from || i >= to); });
      var html = '<span class="pager__info" aria-live="polite">' + (from + 1) + '–' + to + ' sur ' + total + '</span><span class="pager__pages">' + button('prev', '‹', p === 1, false, 'Page précédente');
      var prev = 0;
      [1, p - 1, p, p + 1, pages].filter(function (x, i, a) { return x >= 1 && x <= pages && a.indexOf(x) === i; }).sort(function (a, b) { return a - b; }).forEach(function (x) {
        if (x - prev === 2) html += button(x - 1, x - 1, false, false, 'Page ' + (x - 1));
        else if (x - prev > 2) html += '<span class="pager__gap" aria-hidden="true">…</span>';
        html += button(x, x, false, x === p, 'Page ' + x); prev = x;
      });
      html += button('next', '›', p === pages, false, 'Page suivante') + '</span><label class="pager__size">Lignes par page <select>' + SIZES.concat(0).map(function (v) { return '<option value="' + v + '"' + (v === size ? ' selected' : '') + '>' + (v || 'Tout') + '</option>'; }).join('') + '</select></label>';
      nav.innerHTML = html;
      if (focus) (nav.querySelector('button[data-go="' + focus + '"]:not(:disabled)') || nav.querySelector('[aria-current]')).focus();
      save();
      if (table.dataset.bulk && bars[table.dataset.bulk]) sync(table.dataset.bulk);
    }
    nav.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-go]'); if (!b || b.disabled) return;
      var go = b.dataset.go; p = go === 'prev' ? p - 1 : go === 'next' ? p + 1 : +go;
      render(go);
      if (wrap.getBoundingClientRect().top < 0) wrap.scrollIntoView();
    });
    nav.addEventListener('change', function (e) {
      var firstRow = (p - 1) * (size || body.rows.length);
      size = +e.target.value; mem('localStorage', 'integra.lignes', size);
      p = size ? Math.floor(firstRow / size) + 1 : 1;
      render(); nav.querySelector('select').focus();
    });
    var th = st.c != null && table.tHead && table.tHead.rows[0].cells[st.c];
    if (th && th._sort) { th._sort(!!st.d); col = st.c; dir = !!st.d; }
    table._pgSorted = function (c, asc) { col = c; dir = asc; p = 1; render(); };
    render();
  }
  Array.prototype.forEach.call(document.querySelectorAll('table.grid'), paginate);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') Object.keys(bars).forEach(function (k) { if (!bars[k].hidden) { boxes(k).forEach(function (c) { c.checked = false; }); sync(k); } }); });
})();
