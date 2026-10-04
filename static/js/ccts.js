/* 六月息 · CCTS 历史疆域叠加层
 * 数据源: 中央研究院「中华文明之时空基础架构」(CCTS) WMTS
 *         https://gis.sinica.edu.tw/ccts/wmts  (底本: 谭其骧《中国历史地图集》)
 * 瓦片模板: /ccts/file-exists.php?img={layer}-png-{z}-{x}-{y}
 */
(function () {
    var currentLayer = null;

    var MAP_HINT = '瓦片自台北中研院加载，首次较慢，属正常';

    function map() {
        return typeof chgisMap !== 'undefined' ? chgisMap : null;
    }

    window._cctsOn = false;

    // 统一决定「图区放大」状态: CCTS 或朝代轮廓任一开启即收窄侧栏
    window._applyMapFocus = function () {
        var layout = document.querySelector('.map-layout');
        if (!layout) return;
        var focused = !!window._cctsOn || !!window._dynastyOn;
        if (layout.classList.contains('map-focused') === focused) return;
        layout.classList.toggle('map-focused', focused);
        var m = map();
        if (m) {
            setTimeout(function () { m.invalidateSize(); }, 60);
            setTimeout(function () { m.invalidateSize(); }, 400);
        }
    };

    window.cctsSetLayer = function (layerId) {
        var m = map();
        if (!m) { console.error('CCTS: map not ready'); return; }
        if (currentLayer) {
            m.removeLayer(currentLayer);
            currentLayer = null;
        }
        window._cctsOn = !!layerId;
        window._applyMapFocus();
        if (!layerId) return;
        var url = 'https://gis.sinica.edu.tw/ccts/file-exists.php?img=' + layerId + '-png-{z}-{x}-{y}';
        currentLayer = L.tileLayer(url, {
            opacity: cctsGetOpacity(),
            maxZoom: 12,
            maxNativeZoom: 11,
            attribution: '疆域底图 © 中研院 CCTS（谭其骧图集底本）'
        });
        currentLayer.addTo(m);
        // 疆图层适合全国视野: 仅在视野过小时提示，不强制缩放
        var hint = document.getElementById('cctsHint');
        if (hint) hint.textContent = MAP_HINT;
    };

    window.cctsSetOpacity = function (v) {
        if (currentLayer) currentLayer.setOpacity(parseFloat(v));
        var lab = document.getElementById('cctsOpacityVal');
        if (lab) lab.textContent = Math.round(parseFloat(v) * 100) + '%';
    };

    function cctsGetOpacity() {
        var el = document.getElementById('cctsOpacity');
        return el ? parseFloat(el.value) : 0.75;
    }
})();
