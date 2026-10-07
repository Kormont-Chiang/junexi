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
        html += '<div class="lm-line"><span class="lm-conf">' + conf + '</span><span class="lm-text">' + t + '</span></div>';
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
  }
})();
