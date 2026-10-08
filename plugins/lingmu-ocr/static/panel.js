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
    }).catch(function () {
      gujiBtn.disabled = false;
      gujiState.textContent = '请求失败';
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
  }
})();
