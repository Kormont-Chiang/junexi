# 六月息 JuneXi

> 历史研究个人工作台：**史料的检索与联动枢纽**。
> 集成 CBDB 本地化检索、历史地图、Zotero 联动、Obsidian 笔记桥、
> 可插拔插件系统与多库联合检索——让分散的数字史学工具在一个界面里协同。

## 为什么是"枢纽"

Obsidian 与 Zotero 可以在其内部连接，CBDB 与地图、社会网络分析也可以在其内部连接。
六月息的推进只在于**降低连接的门槛**，并让每个使用者能按自己的研究领域自由装配——
像 Zotero 和 Obsidian 那样，以插件扩展，而非以框架约束。

## 界面预览

|仪表盘（工作台首页）|CBDB 检索（人物/职官/地名/社会关系 全家桶）|
|---|---|
|![仪表盘](docs/screenshots/01-dashboard.png)|![CBDB](docs/screenshots/02-cbdb.png)|

|史料地图（高德中文暗夜底图 + CHGIS 朝代图层）|插件管理（Zotero 式列表）|
|---|---|
|![地图](docs/screenshots/03-map.png)|![插件](docs/screenshots/04-plugins.png)|

## 功能全景

| 模块 | 说明 |
|---|---|
| 🏛️ CBDB 检索 | 中国历代人物传记资料库（613MB 本地化）：人名/职官/地名/入仕/社会区分/著作/年份在世八大检索，亲属递归（五服标注）、社会关系、两人亲属路径 |
| 🗺️ 历史地图 | CHGIS 数据 + 高德中文底图：群体上地图、人生轨迹视图、点图反查 CBDB、生卒年↔朝代图层联动 |
| 📚 读文献 | Zotero 全库列表（73+ 条目）、内嵌 PDF 阅读器、边读边记直写 Obsidian |
| 📖 史料库 | 70 个精选数据库导航（按经史子集/出土文献/域外/期刊/古文字分类），库内检索，AI 导购 |
| 🔍 联合检索 | 一次输入多库并行：CBDB 本地计数、Kanripo 汉籍库、ctext、订阅库带词直达 |
| 🛠️ 史学工具 | 避讳/音韵/年号/职官/地名/版本目录六件，结果附来源声明与在线核查路径 |
| 🤖 AI 助手 | 多模型可选（DeepSeek 对话/深思、OpenClaw 网关），历史研究提示词库 17 条，荣新江《学术训练与学术规范》知识库注入 |
| 🧩 插件系统 | 插件 = 带 manifest.json 的文件夹，管理页可视化开关+一键卸载（用户目录插件）；**插件市场**：URL/本机安装 .jxplugin，市场卡片识别已安装/升级状态，registry 即本仓库 plugins-registry.json（PR 提条目上架）；开发见 [插件开发指南](docs/插件开发指南.md) |
| 📓 学术动态 | arXiv 数字人文/数字史学 + Medievalists.net + JSTOR Daily + **自定义 RSS 源**（面板自加自删），30min 缓存 |

## ⚠️ 安全说明（杀毒软件警告）

本软件**未购买代码签名证书**（年费数百美元），Windows SmartScreen / 360 等会对“网上下载 + 未知发布者”的程序弹警告，这是预期行为，**不是病毒**。

- 代码全部开源可自查；发布包用 PyInstaller 从仓库源码直接构建
- 若被杀软隔离，请对 JuneXi.exe 添加信任/白名单后重试
- 存疑请把 JuneXi.exe 上传 [virustotal.com](https://www.virustotal.com) 自查，或比对以下 SHA-256 指纹

## 快速开始（开发）

```bash
pip install -r requirements.txt   # Flask + pywebview + requests + sxtwl 等
python app.py                     # 默认 127.0.0.1:5000
```

桌面版（Windows）：`python -m PyInstaller -y JuneXi.spec` 产出 `dist/JuneXi/`。

## 内置插件

| 插件 | 内容 |
| --- | --- |
| 🏛️ CBDB 检索 | 29 路由全功能：人名/官职/地名/入仕/社会区分/著作/亲属递归/社会关系/路径/GeoJSON/网络图，Access 本地库 + 预热 |
| 📖 Zotero 联动 | 本地代理（状态/检索/书库/附件）+ 最近阅读 + PDF 内嵌直读 + 笔记落盘 Obsidian |
| 📰 学术动态 | arXiv 数字人文 + Medievalists.net + JSTOR Daily RSS 聚合，支持自定义源 |
| 👁️ 灵眸 OCR | 本地离线 OCR（PP-OCRv6）：生僻字召回与词头分距显著优于旧引擎；行级校对编辑（改动 ✎ 标记、全文实时同步）；甲言 jiayan CRF 句读标点（见下节）；`capabilities: ["ocr"]` 插件协议的首个实现，可被工具书管线/任意功能调用 |
| ☁️ 百度 OCR | 云端高精度（繁体）选配：`plugins/baidu-ocr`，priority 低于灵眸；未配置 key 或失败自动回落本地；key 存用户数据目录 |

### OCR 插件协议

插件 manifest 声明 `"capabilities": ["ocr"]` 并提供 `ocr_page(image_path)` 即成为 OCR provider，
核心按 `priority` 调度、异常自动回落内置引擎。详见 [docs/OCR插件化方案.md](docs/OCR插件化方案.md)。

### 句读标点（甲言 jiayan，本地离线）

OCR 出字串≠得到可读文本。灵眸面板在识别结果下方提供「句读标点」：
CRF 断句+标点，全程本地。两级数据分离：

- **引擎（~1MB）**：面板点「安装引擎」即从 PyPI 直拉 jiayan sdist + python-crfsuite wheel
  到 `%LOCALAPPDATA%\JuneXi\pylib`（免 pip，冻结应用可自装）；kenlm/sklearn 以桩替代
  （仅训练/eval 需要；推理路径不触，sentencizer 的 pmi 特征返回未登录值 'NA' 等效降权）。
- **模型（数 MB）**：需自备——[jiayan 官方仓库](https://github.com/jiaeyan/Jiayan) README
  百度网盘（码 `p0sc`），将 `cut_model` 与 `punc_model` 放入
  `%LOCALAPPDATA%\JuneXi\jiayan_models\` 即可。

端点：`/api/guji/status`、`/api/guji/install`（POST 触发后台下载）、`/api/guji/punctuate`（POST {text}）。
简体外最佳；繁体输入经 OpenCC 转简标点后再转回。识别质量对标见 [docs/灵眸改进调研-吾与点.md](docs/灵眸改进调研-吾与点.md)。

### 实体标注（词典锚定，自家工具书=实体表）

句读结果一键「标注实体」：文本中的年号标金、地名标绿，点词条弹自家工具书考证片段
（哪本书、原文摘要）。思路——对工具书任务，词典最长匹配比神经网络 NER 更准、零模型、
全本地；这是平台型产品没有的一层。

- 端点：`/api/guji/annotate`（POST {text}），索引按数据文件签名热更新（投放新词库无需重启）
- 消歧规则：年号与地名同位时**年号优先**（史文语境）；年号后的纪年尾词不吞为地名
  （「建安四年」→ 建安[年号] + 四年不标）；**书名号《》内一律标「书名」**——书名优先于
  一切词典（《史记》≠ CBDB 里的明代人"史記"）
- 繁体输入：>12% 繁体字自动走逐字转简通道匹配词典，实体位置再映射回原文
  （词典侧年号/地名/职官本就简繁双索引；人名 53 万全量取自 CBDB）
- **CBDB 联动**：点标注弹层直达自家数据库——人名→生卒/字号谥/籍贯死所履历；
  官名→任职者列表；地名→相关人物（无 CBDB 编号的按名检索直达）
- 数据源：`data/toolbooks/nianhao_clean.jsonl`（二十史朔闰表，3715 年号别名）、
  `data/toolbooks/diming_clean.jsonl`（中国历史地名大辞典 OCR 全本 3277 页管线产出，
  67k 词头，`tooling/diming/` + `_ocr_finish.py` 一键解析清洗入库）、
  `data/toolbooks/cbdb_persons.jsonl` / `cbdb_offices.jsonl` / `cbdb_places.jsonl`
  （`tooling/cbdb_export.py` 从本地 CBDB 导出，53 万人名/3.4 万官名/1.1 万地名，简繁双索引）
- 性能：~16 万词首载 <1s（pickle 索引缓存冷启动 0.6s），热标注 ~2ms
- 导出：标注结果 CSV（含 CBDB ref 列，可直接回流检索）

### 错字校对（词典反向校验）

「校对」对识别结果做词典反向校验：整句最长匹配分词后，未登录串若与某词**仅差一字**
（差异落在未登录串内或紧邻左缘），即列为建议（原字→建议、依据词、书证片段），
人工点「采用」一键写回编辑层（自动重建行、作废旧句读/标注）。
词典无频率先验，同分建议并列展示由人裁决（建议机，不冒充裁判）。
端点 `/api/guji/proofread`（POST {text}，上限 3000 字）。

## 数据依赖（不在仓库内）

- **CBDB** 数据集：从 [CBDB 官网](https://projects.iq.harvard.edu/cbdb/) 下载 Access 版，
  放至 `Documents/historia-data/cbdb/`（可用环境变量 `CBDB_DATA_PATH` 覆盖）
- **CHGIS** 数据：同目录 `chgis_data/`（V6 版）
- **Zotero**：需本地客户端运行并启用 local API（默认端口 23119）
- **Obsidian**：需 Local REST API 插件（端口 27123），或直接用文件系统模式
- **DeepSeek API**（可选）：`.env` 里 `DEEPSEEK_API_KEY=`，缺省时回退 OpenClaw 网关

## 测试

```bash
python _test_phase1.py   # CBDB 检索回归（14 项）
python _test_phase7.py   # 亲属递归（19 项）
# …共 9 个测试文件 109+ 项，全绿再合并
```

## 技术栈

Flask · pywebview（WebView2）· PyInstaller · Leaflet + 高德瓦片 · ECharts 力导向图 ·
sxtwl（天文历排盘也用它）· Access via pyodbc/win32com

## 作者与致谢

作者：Korm · 开发协作：Auto-Korm（AI 结对编程）

致谢：CBDB（哈佛燕京学社等）· CHGIS（哈佛燕京学社）· 中国哲学书电子化计划 ·
Kanripo 汉籍 Repository · 荣新江《学术训练与学术规范》（知识库内容来源）

## License

[MIT](LICENSE) — 自由使用、修改与再分发，保留署名即可。

---

*"去以六月息者也"——《庄子·逍遥游》*


## 发布包完整性

| 文件 | SHA-256 |
|---|---|
| JuneXi-v0.2.3-windows.zip（最新 Release） | `68cbd8cdc0c4487d054c0a80a74101679cabb546a4ea9e8a2be83487f9e6748c` |
| JuneXi.exe（含于 zip，自 v0.2.0 未变） | `d875f95d04e30a2a3b8a806f5130af88573119e776093da7920db503a6c748e4`（Windows Defender 2026-10-05 全量扫描无威胁） |
