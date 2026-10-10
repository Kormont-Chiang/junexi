/* 灵眸 OCR 面板逻辑：等核心派发 jx-plugin-page 事件后初始化（innerHTML 不执行 inline script） */
(function () {
  function init() {
    if (document.getElementById('lmDrop').dataset.lmBound === '1') return;
    document.getElementById('lmDrop').dataset.lmBound = '1';
    boot();
  }
  document.addEventListener('jx-plugin-page', function (e) {
    if (e.detail && e.detail.pid === 'lingmu-ocr') setTimeout(init, 0);
  });
  // 兜底：若事件先于监听器派发（插件页是后加载的插件 js），DOM 已存在则直接 init
  if (document.getElementById('lmDrop')) setTimeout(init, 0);

  function boot() {
  var drop = document.getElementById('lmDrop');
  var file = document.getElementById('lmFile');
  var runBtn = document.getElementById('lmRun');
  var picked = null;

  fetch('/api/ocr/providers').then(function (r) { return r.json(); }).then(function (d) {
    var el = document.getElementById('lmStatus');
    var names = (d.providers || []).map(function (p) { return p.id; });
    el.innerHTML = '<span>Providers：<b>' + (names.join('、') || '无') + '</b></span>' +
      '<span>内置引擎：<b>' + (d.builtin ? '可用' : '缺依赖') + '</b></span>' +
      '<span>调度顺序：priority 降序，异常自动回落</span>';
  }).catch(function () {
    document.getElementById('lmStatus').textContent = 'provider 状态加载失败';
  });

  function pick(f) {
    if (!f) return;
    picked = f;
    runBtn.disabled = false;
    drop.querySelector('p').textContent = '已选择：' + f.name + '（' + Math.round(f.size / 1024) + ' KB）';
  }
  drop.addEventListener('click', function () { file.click(); });
  file.addEventListener('change', function () { pick(file.files[0]); });
  ['dragover', 'dragleave', 'drop'].forEach(function (ev) {
    drop.addEventListener(ev, function (e) {
      e.preventDefault();
      drop.classList.toggle('over', ev === 'dragover');
      if (ev === 'drop') pick(e.dataTransfer.files[0]);
    });
  });

  runBtn.addEventListener('click', function () {
    if (!picked) return;
    runBtn.disabled = true;
    runBtn.textContent = '识别中…';
    var fd = new FormData();
    fd.append('file', picked);
    fetch('/api/ocr/upload', { method: 'POST', body: fd }).then(function (r) { return r.json(); }).then(function (d) {
      runBtn.disabled = false;
      runBtn.textContent = '开始识别';
      if (!d.ok) { alert('识别失败：' + (d.error || 'unknown')); return; }
      document.getElementById('lmResult').style.display = 'block';
      document.getElementById('lmProvider').textContent = 'via ' + d.provider;
      document.getElementById('lmMeta').textContent = d.lines.length + ' 行';
      var html = '', full = [];
      d.lines.forEach(function (l) {
        var conf = (typeof l.conf === 'number') ? l.conf.toFixed(2) : '—';
        var t = (l.text || '').replace(/</g, '&lt;');
        html += '<div class="lm-line"><span class="lm-conf">' + conf + '</span><span class="lm-text" contenteditable="true" spellcheck="false">' + t + '</span></div>';
        full.push(l.text || '');
      });
      document.getElementById('lmLines').innerHTML = html;
      document.getElementById('lmFull').value = full.join('\n');
    }).catch(function () {
      runBtn.disabled = false;
      runBtn.textContent = '开始识别';
      alert('识别请求失败');
    });
  });

  document.getElementById('lmCopy').addEventListener('click', function () {
    var ta = document.getElementById('lmFull');
    ta.select();
    document.execCommand('copy');
    this.textContent = '已复制';
    var self = this;
    setTimeout(function () { self.textContent = '复制全文'; }, 1200);
  });

  // ── 句读标点（甲言）：引擎状态轮询 + 一键安装 + 标点 ──
  var gujiCard = document.getElementById('lmGuji');
  var gujiBtn = document.getElementById('lmGujiBtn');
  var gujiInstall = document.getElementById('lmGujiInstall');
  var gujiState = document.getElementById('lmGujiState');
  var gujiOut = document.getElementById('lmGujiOut');
  var hasResult = false;

  function refreshGujiStatus() {
    fetch('/api/guji/status').then(function (r) { return r.json(); }).then(function (d) {
      if (!gujiCard) return;
      var st = d.state;
      if (st === 'ready') {
        gujiState.textContent = '引擎就绪';
        gujiBtn.disabled = !hasResult;
        gujiInstall.style.display = 'none';
      } else if (st === 'no_models') {
        gujiState.textContent = '引擎就绪 · 缺模型';
        gujiBtn.disabled = true;
        gujiInstall.style.display = 'none';
      } else if (d.install && d.install.running) {
        gujiState.textContent = '安装中：' + (d.install.step || '…');
        gujiBtn.disabled = true;
        gujiInstall.style.display = 'none';
        setTimeout(refreshGujiStatus, 1500);
      } else if (st === 'not_installed') {
        gujiState.textContent = '引擎未安装';
        gujiBtn.disabled = true;
        gujiInstall.style.display = '';
      } else {
        gujiState.textContent = '状态异常：' + (d.error || '').slice(0, 60);
        gujiBtn.disabled = true;
        gujiInstall.style.display = '';
      }
    }).catch(function () { gujiState.textContent = '状态查询失败'; });
  }
  refreshGujiStatus();

  gujiInstall.addEventListener('click', function () {
    this.style.display = 'none';
    fetch('/api/guji/install', { method: 'POST' }).then(function () {
      gujiState.textContent = '安装中…';
      setTimeout(refreshGujiStatus, 1200);
    });
  });

  gujiBtn.addEventListener('click', function () {
    var text = document.getElementById('lmFull').value;
    if (!text) return;
    gujiBtn.disabled = true;
    gujiState.textContent = '句读中…';
    fetch('/api/guji/punctuate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text })
    }).then(function (r) { return r.json(); }).then(function (d) {
      gujiBtn.disabled = false;
      if (!d.ok) { gujiState.textContent = '失败：' + (d.error || '').slice(0, 60); refreshGujiStatus(); return; }
      gujiState.textContent = d.traditional ? '完成（繁体已转回）' : '完成';
      gujiOut.value = d.punctuated;
      annoBtn.style.display = '';
      annoBtn.disabled = false;
      proofBtn.style.display = '';
      annoExportBtn.style.display = 'none';
      obsidianBtn.style.display = 'none';
      proofDiv.style.display = 'none';
      annoOn = false;
      annoDiv.style.display = 'none';
      gujiOut.style.display = '';
    }).catch(function () {
      gujiBtn.disabled = false;
      gujiState.textContent = '请求失败';
    });
  });

  // ── 实体标注（词典锚定）：句读结果 × 自家词库 ──
  var annoBtn = document.getElementById('lmGujiAnno');
  var annoExportBtn = document.getElementById('lmAnnoExport');
  var obsidianBtn = document.getElementById('lmObsidianBtn');
  var annoDiv = document.getElementById('lmAnno');
  var annoOn = false;
  var annoEntities = [];
  var popEl = null;

  function esc(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  function closePop() { if (popEl) { popEl.remove(); popEl = null; } }

  function showPop(ent, x, y) {
    closePop();
    popEl = document.createElement('div');
    popEl.className = 'lm-pop';
    var gloss = ent.gloss ? esc(ent.gloss) : '<i>（词条无摘要，见原书考证）</i>';
    var html = '<b>[' + ent.type + '] ' + esc(ent.head) + '</b>　<span style="color:var(--muted,#8a8577)">' + esc(ent.book) + '</span><br>' + gloss;
    if (ent.type === '人名' && ent.ref) {
      html += '<div class="lm-cbdb" id="lmCbdb' + ent.ref + '" style="margin-top:4px;color:var(--muted,#8a8577)">查 CBDB 履历中…</div>';
    } else if (ent.type === '官名' || ent.type === '地名') {
      html += '<div class="lm-cbdb" id="lmLink' + ent.start + '" style="margin-top:4px;color:var(--muted,#8a8577)">查 CBDB 关联人物中…</div>';
    }
    popEl.innerHTML = html;
    document.body.appendChild(popEl);
    if (ent.type === '人名' && ent.ref) {
      fetch('/api/cbdb/person/' + ent.ref).then(function (r) { return r.json(); }).then(function (d) {
        var box = document.getElementById('lmCbdb' + ent.ref);
        if (!box || !d || (!d.name_chn && !d.dynasty)) { if (box) box.remove(); return; }
        var bits = [];
        if (d.dynasty) bits.push(esc(d.dynasty));
        if (d.birthyear || d.deathyear) bits.push((d.birthyear || '?') + '-' + (d.deathyear || '?'));
        var alt = (d.alt_names || []).filter(function (a) { return a.type && a.name; })
          .slice(0, 4).map(function (a) { return esc(a.type) + ' ' + esc(a.name); });
        var addr = (d.addresses || []).filter(function (a) { return a.type; }).slice(0, 2)
          .map(function (a) { return esc(a.type.replace(/\(.*\)/, '')) + ' ' + esc(a.place); });
        var h = '<span style="color:var(--accent,#4a7a68)">' + bits.join(' · ') + '</span>';
        if (alt.length) h += '<br>' + alt.join('　');
        if (addr.length) h += '<br>' + addr.join('　');
        h += '<br><span style="opacity:.7">CBDB #' + ent.ref + '</span>';
        box.innerHTML = h;
      }).catch(function () {
        var box = document.getElementById('lmCbdb' + ent.ref);
        if (box) box.remove();
      });
    } else if (ent.type === '官名' || ent.type === '地名') {
      var boxId = 'lmLink' + ent.start;
      var label = ent.type === '官名' ? '职官' : '地名';
      var personsUrl = null;
      function loadPersons() {
        if (!personsUrl) return;
        fetch(personsUrl).then(function (r) { return r.json(); }).then(function (list) {
          var box = document.getElementById(boxId);
          if (!box) return;
          list = Array.isArray(list) ? list : (list.persons || []);
          if (!list.length) { box.textContent = 'CBDB 暂无关联人物'; return; }
          var top = list.slice(0, 4).map(function (p) {
            return esc(p.name_chn || p.name || '') + ' <span style="opacity:.75">' +
              esc(p.dynasty || '') + (p.birthyear ? ' ' + p.birthyear + '-' + (p.deathyear || '?') : '') + '</span>';
          });
          box.innerHTML = '<span style="color:var(--accent,#4a7a68)">CBDB ' + label + '关联 ' + list.length + ' 人</span>：' + top.join('　');
        }).catch(function () {
          var box = document.getElementById(boxId);
          if (box) box.remove();
        });
      }
      if (ent.type === '地名' && ent.ref) {
        personsUrl = '/api/cbdb/places/' + ent.ref + '/persons';
        loadPersons();
      } else {
        var searchUrl = ent.type === '官名'
          ? '/api/cbdb/offices/search?q=' + encodeURIComponent(ent.head)
          : '/api/cbdb/places/search?q=' + encodeURIComponent(ent.head);
        fetch(searchUrl).then(function (r) { return r.json(); }).then(function (arr) {
          var box = document.getElementById(boxId);
          if (!box) return;
          arr = Array.isArray(arr) ? arr : [];
          var hit = null;
          for (var i = 0; i < arr.length; i++) {
            var nm = arr[i].office_chn || arr[i].name_chn || '';
            if (nm === ent.head || nm === ent.text) { hit = arr[i]; break; }
          }
          hit = hit || arr[0];
          if (!hit) { box.textContent = 'CBDB 无此' + label + '记录'; return; }
          personsUrl = ent.type === '官名'
            ? '/api/cbdb/offices/' + hit.office_id + '/persons'
            : '/api/cbdb/places/' + hit.addr_id + '/persons';
          loadPersons();
        }).catch(function () {
          var box = document.getElementById(boxId);
          if (box) box.remove();
        });
      }
    }
    var w = popEl.offsetWidth, h = popEl.offsetHeight;
    popEl.style.left = Math.min(x, window.innerWidth - w - 12) + 'px';
    popEl.style.top = Math.min(y, window.innerHeight - h - 12) + 'px';
    setTimeout(function () {
      document.addEventListener('click', function h(ev) {
        if (popEl && !popEl.contains(ev.target)) { closePop(); document.removeEventListener('click', h); }
      });
    }, 0);
  }

  annoDiv.addEventListener('click', function (e) {
    var t = e.target;
    if (t && t.classList && t.classList.contains('lm-ent')) {
      var ent = annoEntities[+t.getAttribute('data-i')];
      if (ent) showPop(ent, e.clientX + 8, e.clientY + 10);
    }
  });

  annoBtn.addEventListener('click', function () {
    var text = gujiOut.value;
    if (!text) return;
    if (annoOn) { annoOn = false; annoDiv.style.display = 'none'; gujiOut.style.display = ''; annoBtn.textContent = '标注实体'; annoExportBtn.style.display = 'none'; return; }
    annoBtn.disabled = true;
    annoBtn.textContent = '标注中…';
    fetch('/api/guji/annotate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text })
    }).then(function (r) { return r.json(); }).then(function (d) {
      annoBtn.disabled = false;
      annoBtn.textContent = '标注实体';
      if (!d.ok) { annoDiv.style.display = 'none'; return; }
      annoEntities = d.entities || [];
      var html = '', pos = 0;
      annoEntities.forEach(function (ent, i) {
        if (ent.start < pos) return;  // 重叠丢弃
        html += esc(text.slice(pos, ent.start));
        html += '<span class="lm-ent lm-ent-' + ent.type + '" data-i="' + i + '" title="' + esc(ent.book) + '">' + esc(ent.text) + '</span>';
        pos = ent.end;
      });
      html += esc(text.slice(pos));
      if (d.truncated) html += ' <i style="color:var(--muted,#8a8577)">（已达上限）</i>';
      annoDiv.innerHTML = html;
      annoDiv.style.display = 'block';
      gujiOut.style.display = 'none';
      annoOn = true;
      annoExportBtn.style.display = annoEntities.length ? '' : 'none';
      obsidianBtn.style.display = annoEntities.length ? '' : 'none';
      var counts = {};
      annoEntities.forEach(function (e) { counts[e.type] = (counts[e.type] || 0) + 1; });
      gujiState.textContent = '实体 ' + annoEntities.length + ' 处' +
        (d.truncated ? '（词库命中过多，仅标前 ' + annoEntities.length + ' 处；可分段处理）' : '') +
        '：' + Object.keys(counts).map(function (k) { return k + ' ' + counts[k]; }).join(' / ');
    }).catch(function () {
      annoBtn.disabled = false;
      annoBtn.textContent = '标注实体';
    });
  });

  annoExportBtn.addEventListener('click', function () {
    if (!annoEntities.length) return;
    var rows = ['text,type,book,head,gloss,ref,start,end'];
    annoEntities.forEach(function (e) {
      rows.push([e.text, e.type, e.book, e.head, (e.gloss || '').replace(/[\r\n]/g, ' '),
                 e.ref || '', e.start, e.end].map(function (v) {
        v = String(v);
        return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
      }).join(','));
    });
    var blob = new Blob(['﻿' + rows.join('\n')], { type: 'text/csv;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'lingmu_entities.csv';
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 5000);
  });

  // ── 存入 Obsidian：标注结果 → vault/灵眸标注/*.md ──
  obsidianBtn.addEventListener('click', function () {
    if (!annoEntities.length) return;
    var btn = this;
    btn.disabled = true;
    var old = btn.textContent;
    btn.textContent = '写入中…';
    fetch('/api/plugins/lingmu-ocr/save_obsidian', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: gujiOut.value, entities: annoEntities })
    }).then(function (r) { return r.json(); }).then(function (d) {
      btn.disabled = false;
      if (d.ok) {
        btn.textContent = '✓ 已存入';
        gujiState.textContent = '已存入 Obsidian：' + d.path;
        setTimeout(function () { btn.textContent = old; }, 2500);
      } else {
        btn.textContent = 'Obsidian 未连接';
        gujiState.textContent = '存入失败：' + (d.error || '未知错误');
        setTimeout(function () { btn.textContent = old; }, 3000);
      }
    }).catch(function () {
      btn.disabled = false;
      btn.textContent = old;
      gujiState.textContent = '存入失败：网络错误';
    });
  });

  // ── 示例载入：一键填入真古籍片段，走全链验收零成本 ──
  var SAMPLE_TEXT = '建安元年秋七月，天子还洛阳。太祖乃诣洛阳，卫京都。二年春，袁绍与公孙瓒战于界桥。三年夏四月，司徒王允与吕布共杀卓。卓将李傕、郭汜等攻长安，城陷，杀允。太祖迎天子都许。';
  var SAMPLE_TRAD = '建安四年春，帝至洛陽。曹操為大將軍，袁紹據河北。備將關羽屯下邳，行太守事。';
  document.getElementById('lmGujiSample').addEventListener('click', function () {
    document.getElementById('lmFull').value = SAMPLE_TEXT;
    rebuildRowsFromFull();
  });
  document.getElementById('lmGujiSampleTrad').addEventListener('click', function () {
    document.getElementById('lmFull').value = SAMPLE_TRAD;
    rebuildRowsFromFull();
  });

  // ── 校对（词典反向校验）：未收录串 + 单错建议，可采用 ──
  var proofBtn = document.getElementById('lmProofBtn');
  var proofDiv = document.getElementById('lmProof');
  var proofData = null;

  function rebuildRowsFromFull() {
    var lines = document.getElementById('lmFull').value.split('\n');
    var html = '';
    lines.forEach(function (t) {
      var x = t.replace(/</g, '&lt;');
      html += '<div class="lm-line"><span class="lm-conf">—</span><span class="lm-text" contenteditable="true" spellcheck="false">' + x + '</span></div>';
    });
    document.getElementById('lmLines').innerHTML = html;
  }

  var proofUndoStack = [];
  proofDiv.addEventListener('click', function (e) {
    var b = e.target;
    if (!b || !b.classList || !b.classList.contains('lm-p-use')) return;
    var idx = +b.getAttribute('data-i');
    var sg = proofData && proofData.suggestions[idx];
    if (!sg) return;
    var lmFullEl = document.getElementById('lmFull');
    var v = lmFullEl.value;
    if (v.charAt(sg.pos) !== sg.orig) { b.textContent = '已偏移'; b.disabled = true; return; }
    proofUndoStack.push({ snapshot: v, label: sg.orig + '→' + sg.char });
    if (proofUndoStack.length > 20) proofUndoStack.shift();
    lmFullEl.value = v.slice(0, sg.pos) + sg.char + v.slice(sg.pos + 1);
    rebuildRowsFromFull();
    if (gujiOut.value) gujiOut.value = '';
    if (annoOn) { annoOn = false; annoDiv.style.display = 'none'; gujiOut.style.display = ''; }
    b.textContent = '已采用';
    b.disabled = true;
    var undoBtn = document.getElementById('lmProofUndo');
    if (undoBtn) undoBtn.style.display = '';
    gujiState.textContent = '已采用建议（全文已更新，可重新句读）';
  });

  var proofUndoBtn = document.getElementById('lmProofUndo');
  proofUndoBtn.addEventListener('click', function () {
    var item = proofUndoStack.pop();
    if (!item) { this.style.display = 'none'; return; }
    document.getElementById('lmFull').value = item.snapshot;
    rebuildRowsFromFull();
    if (gujiOut.value) gujiOut.value = '';
    if (annoOn) { annoOn = false; annoDiv.style.display = 'none'; gujiOut.style.display = ''; }
    if (!proofUndoStack.length) this.style.display = 'none';
    gujiState.textContent = '已撤销：' + item.label;
  });

  proofBtn.addEventListener('click', function () {
    var text = document.getElementById('lmFull').value;
    if (!text) return;
    proofBtn.disabled = true;
    proofBtn.textContent = '校对中…';
    fetch('/api/guji/proofread', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text })
    }).then(function (r) { return r.json(); }).then(function (d) {
      proofBtn.disabled = false;
      proofBtn.textContent = '校对';
      if (!d.ok) { proofDiv.style.display = 'none'; gujiState.textContent = d.error || '校对失败'; return; }
      proofData = d;
      var html = '';
      if (d.suggestions.length) {
        html += '<h4>疑似错字 ' + d.suggestions.length + ' 处（建议供参考，点击采用）</h4>';
        d.suggestions.forEach(function (sg, i) {
          html += '<div class="lm-p-row">#' + (sg.pos) + ' <span class="lm-p-fix">' + esc(sg.orig) + '→' + esc(sg.char) +
            '</span> 依据 <span class="lm-p-w">' + esc(sg.word) + '</span>〔' + esc(sg.type) + '·' + esc(sg.book) + '〕' +
            (sg.gloss ? ' ' + esc(sg.gloss.slice(0, 30)) : '') +
            ' <button class="lm-p-use" data-i="' + i + '">采用</button></div>';
        });
      }
      if (d.unknown.length) {
        html += '<h4>未收录串 ' + d.n_unknown + ' 处（词库无据，多为专名或连续错字）</h4>';
        d.unknown.slice(0, 12).forEach(function (u) {
          html += '<div class="lm-p-row lm-p-unk">#' + u.start + ' 「' + esc(u.text.slice(0, 20)) + '」</div>';
        });
      }
      proofDiv.innerHTML = html || '<div class="lm-p-row">未发现可疑处。</div>';
      proofDiv.style.display = 'block';
      gujiState.textContent = '校对完成：疑似 ' + d.suggestions.length + ' / 未收录 ' + d.n_unknown;
    }).catch(function () {
      proofBtn.disabled = false;
      proofBtn.textContent = '校对';
    });
  });

  // OCR 结果落位后：亮出句读卡 + 解锁按钮
  var mo = new MutationObserver(function () {
    if (document.getElementById('lmLines').children.length > 0) {
      hasResult = true;
      gujiCard.style.display = 'block';
      if (gujiBtn.disabled) refreshGujiStatus();
    }
  });
  mo.observe(document.getElementById('lmLines'), { childList: true });

  // ── 行级校对编辑：contenteditable 行 → 实时同步 lmFull；改动行记 ✎；旧句读作废 ──
  var lmLinesEl = document.getElementById('lmLines');
  function syncFull() {
    var texts = [];
    lmLinesEl.querySelectorAll('.lm-text').forEach(function (s) { texts.push(s.textContent); });
    document.getElementById('lmFull').value = texts.join('\n');
    if (gujiOut.value) gujiOut.value = '';   // 文本已变，旧句读结果作废
  }
  lmLinesEl.addEventListener('input', function (e) {
    var row = e.target.closest ? e.target.closest('.lm-line') : null;
    if (row && !row.classList.contains('edited')) {
      row.classList.add('edited');
      var badge = row.querySelector('.lm-conf');
      if (badge) { badge.textContent = '✎'; badge.title = '已人工修改'; }
    }
    syncFull();
  });
  lmLinesEl.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') { e.preventDefault(); e.target.blur(); }
  });
  lmLinesEl.addEventListener('paste', function (e) {
    e.preventDefault();
    var txt = (e.clipboardData || window.clipboardData).getData('text/plain');
    document.execCommand('insertText', false, txt.replace(/\s+/g, ''));
  });
  }
})();
