# R40a 硬编码颜色审计报告

> 2026-10-11 · 目标：为 R40b 四预设主题 CSS 变量化摸清全部硬编码颜色面

## 审计范围

| 文件 | hex 出现 | rgba() 出现 | 内联 style 含色 |
|------|----------|-------------|-----------------|
| `static/css/style.css` | 895 | 702 | 0 |
| `static/css/app.css` | 18 | 0 | 0 |
| `templates/index.html` | 32 | 71 | 69 rgba + 3 hex |
| `static/js/app.js` | 61 | 8 | 21 hex |
| `static/js/reading.js` | 36 | 4 | 6 hex |
| `static/js/zotero.js` | 15 | 2 | 0 |
| `static/js/data/chgis/chgis-data.js` | 33 | 21 | 0 |
| `plugins/lingmu-ocr/static/panel.js` | 6 | 0 | 6 hex |

## style.css 现状（主体）

- **8 个完全相同的 `:root` 块**（重复定义，应合并为 1 个）
- 已有 CSS 变量系统：`--bg-primary/secondary/tertiary/card/hover`、`--border-color`、`--text-primary/secondary/muted`、`--accent/dim/glow`、`--danger/success/info`、`--radius/sm`、`--shadow/lg`
- **var() 引用 3293 次**——说明变量体系已被广泛使用，基础架构好
- 但仍有 895 处 hex + 702 处 rgba 硬编码散布在各 selector 中

### 硬编码颜色分类

**① 与现有变量重复（应替换为 var() 引用）**
约 60% 的硬编码值与 `:root` 变量值完全等同或极近似：
- `#0f0f12`/`#0f0f13` ≈ `--bg-primary`
- `#16161a`/`#16161c` ≈ `--bg-secondary`
- `#1e1e24` ≈ `--bg-tertiary`
- `#1a1a20` ≈ `--bg-card`
- `#25252e` ≈ `--bg-hover`
- `#2a2a35` ≈ `--border-color`
- `#e8e8ec` ≈ `--text-primary`
- `#a0a0b0` ≈ `--text-secondary`
- `#6b6b7b` ≈ `--text-muted`
- `#c9a96e` ≈ `--accent`
- `#8b7355` ≈ `--accent-dim`
- `#c75450` ≈ `--danger`
- `#5a9e6e` ≈ `--success`
- `#5a8ec7` ≈ `--info`

**② 近似变体（应提升为新变量或收敛到最近变量）**
- 背景系：`#06070c` `#141419` `#17150f` `#17171d` `#1a150c` `#1b1b22` `#1d1b17` `#241a08` `#2e2e3a`
- 文字系：`#8a8578` `#8a8a96` `#8f8fa0` `#b8b2a4` `#c8c4b8` `#c9c9d4` `#d8d2c4` `#ddd7ca` `#e4e0d8` `#e8e3d8` `#e8e4d8` `#ece7db` `#ece8dc`
- 金色系（accent 变体）：`#c9a86a` `#d0a050` `#d4b47e` `#e8a93c` `#e8c87e` `#ecd9a8` `#f0e6cc` `#ffe9b8`
- 功能色变体：`#b03a2e` `#c07a6a` `#c9962e` `#b97f22` `#7c3aed`

**③ rgba 阴影/遮罩层（可参数化或保留）**
- 黑色遮罩系列：`rgba(0,0,0,0.28~0.8)` 共 12 档——用于 modal 遮罩、阴影
- accent 透明度系列：`rgba(201,169,110,0.04~0.6)` 共 25 档——大量用于 glow、边框、hover
- 其他色透明度：`rgba(90,142,199,*)` info 系、`rgba(199,84,80,*)` danger 系等

**④ 语义色/独立色（需新增变量）**
- `#4a9` `#5cb87a` `#7da87b` `#7ec8e3` `#7ec9c3` 等图表/标签独立色
- 地图相关、`#7c3aed` 紫等

### app.css（484B）
feed 源标签六色组，每组三色（bg+color+border），共 18 hex。已带 alpha 后缀（`22`/`55`）。

## index.html 内联颜色（103 处）

- **69 处 `style="background:rgba(...,0.14)"`**——动态生成的类别标签底色，颜色在 JS 中拼接
- 3 处 hex 内联
- 若干 `var(--muted)` `var(--bg)` 等旧变量引用（**注意变量名与 style.css 的变量体系不一致**）

### ⚠ 双变量体系冲突
index.html / app.js 使用的变量名：`--bg` `--fg` `--text` `--muted` `--panel` `--border` `--accent`
style.css 定义的变量名：`--bg-primary` `--text-primary` `--text-muted` `--border-color` `--accent`

**R40b 必须统一命名空间**，否则主题切换时一套变量改了另一套没改，出现漏色。

## JS 文件硬编码颜色

| 文件 | 说明 |
|------|------|
| `app.js` (61+21处) | ECharts 图配色、地图标记色、动态 DOM style 赋值 |
| `reading.js` (36+6处) | 阅读器标注色、高亮色 |
| `chgis-data.js` (33+21处) | 朝代疆域 GeoJSON 填充色 |
| `zotero.js` (15+2处) | 标签色、状态色 |
| `lingmu-ocr/panel.js` (6+6处) | OCR 结果高亮色 |

## R40b 实施方案要点

1. **统一变量命名**：以 style.css 的 `--bg-primary` 系为主，index.html/app.js 的旧短名映射过来（`--bg`→`--bg-primary`，`--text`→`--text-primary`，`--muted`→`--text-muted`，`--border`→`--border-color`）
2. **合并 8 个 :root 块为 1 个**，补齐缺失变量（语义色、图表色、遮罩透明度档位）
3. **四预设主题**通过 `data-theme` attribute + CSS 变量覆盖实现：
   - `dark`（默认，当前暗色）
   - `light` 白纸（亮色）
   - `sepia` 美拉德（暖棕）
   - `morandi` 莫兰迪（灰调柔和）
4. **替换优先级**：先 index.html 内联 69 处（最大漏色源）→ style.css 重复变量值 → JS 动态色
5. **JS 硬编码**：能改 CSS 变量的改变量；图表/地图的数据驱动色（chgis 朝代色等）保留原值但加 CSS 变量兜底
6. **app.css feed 六色组**：改为 CSS 变量 `--feed-c0` ~ `--feed-c5`
