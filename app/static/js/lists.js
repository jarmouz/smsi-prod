/* Listes : tri par colonne, sélection et actions en masse, ouverture dans un nouvel onglet (3.18). */
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
      function sort() {
        var asc = th.getAttribute('aria-sort') !== 'ascending';
        Array.prototype.forEach.call(head.rows[0].cells, function (o) { o.removeAttribute('aria-sort'); });
        th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');
        var idx = th.cellIndex;
        Array.prototype.slice.call(body.rows).filter(function (r) { return r.cells.length > 1; })
          .sort(function (a, b) { var r = cellKey(a, idx).localeCompare(cellKey(b, idx), 'fr', { numeric: true, sensitivity: 'base' }); return asc ? r : -r; })
          .forEach(function (r) { body.appendChild(r); });
      }
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
    b.innerHTML = '<b class="bulk-bar__n"></b><select class="bulk-bar__act" aria-label="Action"><option value="">Choisir une action…</option><option value="export">Exporter en CSV</option></select><select class="bulk-bar__val" aria-label="Valeur" hidden></select><button type="button" class="btn btn--primary btn--sm bulk-bar__go" disabled>Appliquer</button><button type="button" class="btn btn--ghost btn--sm bulk-bar__clear">Désélectionner</button>';
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
    b.querySelector('.bulk-bar__clear').addEventListener('click', function () { boxes(kind).forEach(function (c) { c.checked = false; }); sync(kind); });
    return (bars[kind] = b);
  }
  function boxes(kind) { return Array.prototype.slice.call(document.querySelectorAll('input.bulk-cb[data-kind="' + kind + '"]')); }
  function selected(kind) { return boxes(kind).filter(function (c) { return c.checked; }).map(function (c) { return c.value; }); }
  function sync(kind) {
    var n = selected(kind).length, b = barFor(kind);
    b.hidden = !n; b.querySelector('.bulk-bar__n').textContent = n + ' sélectionné(s)';
    document.querySelectorAll('input.bulk-all[data-kind="' + kind + '"]').forEach(function (a) { var t = a.closest('table').querySelectorAll('input.bulk-cb'), c = a.closest('table').querySelectorAll('input.bulk-cb:checked').length; a.checked = c > 0 && c === t.length; a.indeterminate = c > 0 && c < t.length; });
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
          var all = Array.prototype.slice.call(table.querySelectorAll('input.bulk-cb')), a = all.indexOf(last), b = all.indexOf(cb);
          all.slice(Math.min(a, b), Math.max(a, b) + 1).forEach(function (x) { x.checked = cb.checked; });
          sync(kind);
        }
        last = cb;
      });
      cb.addEventListener('change', function () { sync(kind); });
    });
    Array.prototype.forEach.call(body.rows, function (r) { if (!r.dataset.id && r.cells.length === 1) r.cells[0].colSpan += 1; });
    var all = table.querySelector('input.bulk-all');
    if (all) { all.addEventListener('click', function (e) { e.stopPropagation(); }); all.closest('th').addEventListener('click', function (e) { e.stopPropagation(); });
      all.addEventListener('change', function () { table.querySelectorAll('input.bulk-cb').forEach(function (c) { c.checked = all.checked; }); sync(kind); }); }
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') Object.keys(bars).forEach(function (k) { if (!bars[k].hidden) { boxes(k).forEach(function (c) { c.checked = false; }); sync(k); } }); });
})();
