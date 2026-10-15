/* ═══════════════ AI agent 插件前端 (R101) ═══════════════
 * 注入"自动操作"开关 + 接管 AI 发送 + 动作分发。
 * 依赖核心 app.js 全局函数: switchTab/switchCBDBType/renderCBDBSearchArea/searchCBDB/
 *   loadCBDBPersonDetail/cbdbPlotTrajectory/cbdbPlotGroupOnMap/escapeHtml/formatAIResponse/aiCopyResponse
 * 本插件被禁用/卸载时: 开关与接管一并消失, AI 页退回纯对话。
 */
(function () {
    'use strict';

    // ── 开关注入 AI 助手左栏(余额面板所在 section 末尾) ──
    function injectToggle() {
        if (document.getElementById('aiAgentMode')) return;
        const anchor = document.getElementById('aiBalancePanel');
        if (!anchor || !anchor.parentElement) return;
        const label = document.createElement('label');
        label.title = '开启后, AI 将直接操作 JuneXi: 检索/打开详情/上图(试验)';
        label.style.cssText = 'display:flex;align-items:center;gap:5px;margin-top:8px;font-size:11px;cursor:pointer;color:var(--text)';
        label.innerHTML = '<input type="checkbox" id="aiAgentMode" style="cursor:pointer">' +
            '<span>🕹 自动操作 JuneXi <span style="color:var(--muted)">(试验)</span></span>';
        anchor.parentElement.appendChild(label);
        const cb = label.querySelector('#aiAgentMode');
        cb.addEventListener('change', function () {
            try { localStorage.setItem('jx_ai_agent', cb.checked ? '1' : '0'); } catch (e) {}
            if (cb.checked && typeof showToast === 'function') showToast('自动操作已开启: AI 回答后会直接操作 JuneXi(试验)', 'info', 2500);
        });
        try { cb.checked = localStorage.getItem('jx_ai_agent') === '1'; } catch (e) {}
    }

    // AI 页签可能后开: DOM 就绪即注, 若面板还没渲染则轮询几次
    let tries = 0;
    (function poll() {
        injectToggle();
        if (!document.getElementById('aiAgentMode') && tries++ < 20) setTimeout(poll, 500);
    })();

    // ── 泛化检索: 按检索类型切页填词(官名/地名/人名通用) ──
    function searchCBDBByType(type, q) {
        if (window._cbdbType !== type) switchCBDBType(type);
        else renderCBDBSearchArea(type);
        const input = document.getElementById('cbdbSearchInput');
        if (input) input.value = q;
        searchCBDB();
    }

    // ── 动作分发: 后端工具执行成功后按模板驱动现有页面 ──
    async function aiRunActions(actions) {
        for (const a of actions) {
            try {
                if (a.type === 'cbdb_search' && a.name) {
                    if (a.mode) searchCBDBByType(a.mode, a.name);
                    else searchCBDBByName(a.name);
                } else if (a.type === 'cbdb_person' && a.id) {
                    loadCBDBPersonDetail(a.id);
                } else if (a.type === 'cbdb_map' && Array.isArray(a.ids) && a.ids.length) {
                    window._cbdbMapLastIds = a.ids;
                    window._cbdbMapLastTitle = a.ids.length + ' 人(AI)';
                    if (a.ids.length === 1) { await cbdbPlotTrajectory(); }
                    else { await cbdbPlotGroupOnMap(); }
                }
            } catch (e) { console.error('AI action failed:', a, e); }
        }
    }

    // ── agent 模式发送: 走 /api/ai/agent, 展示步数, 执行动作 ──
    async function sendAIChatAgent(text) {
        const box = document.getElementById('aiChatMessages');
        box.innerHTML += `<div class="ai-message user"><div class="ai-bubble">${escapeHtml(text)}</div></div>`;
        const loadingId = 'ai-loading-' + Date.now();
        box.innerHTML += `<div class="ai-message system" id="${loadingId}"><div class="ai-bubble"><div class="loading"></div> 正在操作 JuneXi…</div></div>`;
        box.scrollTop = box.scrollHeight;
        try {
            const res = await apiFetch('/api/ai/agent', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    model: window._aiModel || undefined,
                    history: (Array.isArray(window._aiHistory) ? window._aiHistory : [])
                })
            });
            const data = await res.json();
            const loadingEl = document.getElementById(loadingId);
            if (loadingEl) loadingEl.remove();
            if (data.error) {
                box.innerHTML += `<div class="ai-message system"><div class="ai-bubble">⚠️ ${escapeHtml(data.error)}</div></div>`;
            } else {
                const steps = data.steps || [];
                let stepHtml = '';
                if (steps.length) {
                    stepHtml = `<div style="font-size:11px;color:var(--muted);margin-bottom:4px">⚙️ 已执行 ${steps.length} 步: ` +
                        steps.map(s => `<span style="color:${s.ok ? 'var(--accent, #2e7d4f)' : 'var(--danger)'}">${escapeHtml(s.tool)}${s.ok ? ' ✓' : ' ✗'}</span>`).join(' → ') +
                        '</div>';
                }
                const content = data.response || '(无回复)';
                window._aiHistory = (Array.isArray(window._aiHistory) ? window._aiHistory : [])
                    .concat([{ role: 'user', content: text }, { role: 'assistant', content: content }]).slice(-10);
                box.innerHTML += `<div class="ai-message ai">${stepHtml}<div class="ai-bubble">${formatAIResponse(content)}</div><button class="ai-copy-btn" onclick="aiCopyResponse(this)" title="复制回答">📋</button></div>`;
                if (data.actions && data.actions.length) {
                    showToast(`AI 正在操作 JuneXi(${data.actions.length} 个动作)…`, 'info', 2000);
                    await aiRunActions(data.actions);
                }
            }
        } catch (e) {
            const loadingEl = document.getElementById(loadingId);
            if (loadingEl) loadingEl.remove();
            box.innerHTML += `<div class="ai-message system"><div class="ai-bubble">请求失败: ${escapeHtml(e.message)}</div></div>`;
        }
        box.scrollTop = box.scrollHeight;
    }

    // ── 注册发送接管钩子(核心 sendAIChat 在发送前检查本钩子) ──
    window._aiSendOverride = function (text) {
        const cb = document.getElementById('aiAgentMode');
        if (cb && cb.checked) { sendAIChatAgent(text); return true; }
        return false; // 开关关闭: 不接管, 核心走纯对话
    };
})();
