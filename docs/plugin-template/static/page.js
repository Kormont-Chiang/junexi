/* 插件前端示例：页面注入后由 jx-plugin-page 事件触发初始化 */
(function () {
  function init() {
    if (document.getElementById('mpp-out')) return; // 已初始化
    window.myPluginPing = function () {
      fetch('/api/myplugin/hello').then(function (r) { return r.json(); }).then(function (d) {
        document.getElementById('mpp-out').textContent = d.msg;
      });
    };
  }
  document.addEventListener('jx-plugin-page', function (e) {
    if (e.detail && e.detail.pid === 'my-plugin') setTimeout(init, 0);
  });
})();
