# 六月息 · 历史学学术工作台

基于 Flask 的本地学术面板，集成 Obsidian、CBDB、CHGIS、DeepSeek。
桌面快捷方式双击即开（pywebview 原生窗口），无需浏览器。

## 功能

- **CBDB 十大检索模块**（对标原生引得平台）：人名 / 官名 / 地名 / 社会关系 / 入仕 / 社会区分 / 著作 / 年份在世 / 综合
- **亲属递归检索**——复刻原生四参数（先世/后世/旁系/姻亲）BFS + 五服直查
- **两人关系**——双向社会关系 + 直系亲属直查，带五服称谓
- **地区关系**——某地区相关人物之间的社会关系
- **群体网络**——任意人物列表的组内关系网 + 外延 BFS
- **人群属性**——任意人物列表的扁平总表（可 CSV 导出）
- **Obsidian 双向读写** — 通过 Local REST API 直接读写笔记
- **AI 助手** — 面板内嵌 DeepSeek，读史料、梳理论证
- **历史地理可视化** — CHGIS 朝代边界 + 高德/Esri 底图

## 安装（开发环境）

### 1. Python 依赖

```bash
cd historia-server
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置 `.env`

```env
OBSIDIAN_API_KEY=your_api_key_here   # Obsidian Local REST API 插件的密钥
DEEPSEEK_API_KEY=your_key_here       # 可选，OpenClaw gateway 不可用时直连
```

### 3. 启动

- **桌面版体验**：`python desktop.py`（自动分配空闲端口、单实例锁）
- **纯后端调试**：`python app.py`（默认 5000，可用 `HISTORIA_PORT` 覆盖）

### 4. CBDB 数据

Access 数据库（约 613MB）默认路径：
`C:\Users\Lenovo\Documents\historia-data\cbdb\`
可用环境变量 `CBDB_DATA_PATH` 覆盖。

## 打包与部署

```bash
# 构建（one-dir，产物在 dist\JuneXi\）
venv\Scripts\pyinstaller.exe JuneXi.spec --noconfirm --clean

# Inno Setup 安装包
# 用 packaging\june-xi.iss 编译，产出安装器
```

部署到本机安装版：整目录替换 `%LOCALAPPDATA%\Programs\JuneXi\`（`_internal\` + `JuneXi.exe`）。
用户数据在 `%LOCALAPPDATA%\JuneXi\`，替换不影响。
**注意**：app.py 是冻结代码，改 Python 逻辑必须重新打包；纯前端（`static\` 下 js/css）可直接复制到 `_internal\static\` 免打包。

## 测试

```bash
venv\Scripts\python.exe _test_phase1.py   # 基础检索 14 项
venv\Scripts\python.exe _test_phase2.py   # 亲属递归+五服
venv\Scripts\python.exe _test_phase3.py   # 跨查询传递+导出 13 项
venv\Scripts\python.exe _test_phase4.py   # 社会关系 12 项
venv\Scripts\python.exe _test_phase5.py   # 原生查询逻辑 6 项
venv\Scripts\python.exe _test_phase6.py   # 四大窗体+群体 16 项
```

测试用 Flask test_client，免端口、免启动服务。

## API 端点

### 系统
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 系统状态（Obsidian/CBDB/CHGIS 三项并行探测） |
| `/api/news` | GET/POST | 资讯列表/更新 |

### CBDB · 检索
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/cbdb/search` | GET | 人名检索（简繁/拼音三模式/批量/生卒/索引年/性别/籍贯） |
| `/api/cbdb/query` | POST | 综合查询（全维度 AND 组合 + person_ids 范围交集） |
| `/api/cbdb/year/people` | GET | 年份在世检索 |
| `/api/cbdb/dynasties` | GET | 朝代字典 |

### CBDB · 职官 / 地名 / 入仕 / 社会区分 / 著作
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/cbdb/offices/search` | GET | 官名→官职字典（门类筛选，简繁转换） |
| `/api/cbdb/offices/<id>/persons` | GET | 任职者+任期 |
| `/api/cbdb/places/search` | GET | 地名→ADDR_CODES（层级/坐标/年代） |
| `/api/cbdb/places/nearest` | GET | **坐标反查地名**（x/y→半径内最近地名+距离km，地图点挖入口） |
| `/api/cbdb/places/<id>/persons` | GET | 相关人物（籍贯/居址/任职地，同坐标并入） |
| `/api/cbdb/entries/search` | GET | 入仕方式字典 |
| `/api/cbdb/entries/<code>/persons` | GET | 该入仕方式的人物 |
| `/api/cbdb/status/search` | GET | 社会区分字典 |
| `/api/cbdb/status/<code>/persons` | GET | 该社会区分的人物 |
| `/api/cbdb/texts/search` | GET | 著作检索 |
| `/api/cbdb/texts/<id>/persons` | GET | 著作相关人物 |

### CBDB · 人物
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/cbdb/person/<id>` | GET | 人物详情（基本信息/字号/地址/官职/社会区分/著作） |
| `/api/cbdb/person/<id>/kin` | GET | 直系亲属 |
| `/api/cbdb/person/<id>/kin/recursive` | GET | 亲属递归 BFS（up/down/col/mar 四参数，五服徽标） |
| `/api/cbdb/person/<id>/assoc` | GET | 该人物的社会关系 |
| `/api/cbdb/network/<id>` | GET | 单人关系网络（可含亲属直边，可按朝代过滤外围） |

### CBDB · 关系与群体
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/cbdb/assoc/types` | GET | 社会关系类型字典（490 条，13 大类自动归类） |
| `/api/cbdb/assoc/persons` | GET | 按关系类型查人物对（pair 并入双向） |
| `/api/cbdb/assoc/between` | GET | **两人关系**（双向社会关系 + 直系亲属直查） |
| `/api/cbdb/places/<id>/assoc` | GET | **地区关系**（该地区人物间的社会关系） |
| `/api/cbdb/network/group` | POST | **群体网络**（组内关系边 + 外延 BFS） |
| `/api/cbdb/group/data` | POST | **人群属性**（一人一行的扁平总表） |
| `/api/cbdb/persons/geojson` | POST | 人物 GeoJSON 导出（地图联动） |

### Obsidian
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/obsidian/notes` | GET | 列出/搜索笔记 |
| `/api/obsidian/note/<path>` | GET/PUT/DELETE | 读写删笔记 |
| `/api/obsidian/daily` | POST | 创建今日札记 |
| `/api/obsidian/stats` | GET | 统计 |
| `/api/obsidian/init-folders` | POST | 初始化目录结构 |

### CHGIS
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chgis/status` | GET | 数据状态 |
| `/api/chgis/files` | GET | 文件列表 |
| `/api/chgis/file/<name>` | GET | 读取文件 |
| `/api/chgis/upload` | POST | 上传 |
| `/api/chgis/capitals` | GET | 都城数据 |
| `/api/chgis/dynasty/<key>` | GET | 朝代边界 |
| `/api/chgis/regime` | GET | 政权数据 |

### AI
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/ai/chat` | POST | AI 对话（标准 messages 数组） |
| `/api/ai/summarize` | POST | AI 摘要 |
| `/api/ai/analyze` | POST | AI 分析 |

## 地图联动闭环（检索 → 群体 → 时空分布 → 点回去挖人）

- **群体上地图**：任意 CBDB 人物列表「在地图查看」→ 地址坐标聚合标注（≤40 散点金珠，>40 聚簇圆盘）→ 地址类型筛选（全部/籍贯/祖籍/居址/葬·卒地，`addr_types` 参数）→ 聚点名单可整组**回灌 CBDB 列表**
- **地图反查 CBDB**：地图页「⌖ 点图反查」开关 → 点击任意位置 → 半径内最近 CBDB 地名（距离/层级/存续期，同坐标合并为一条并计数）→ 点地名载入相关人物（同坐标并入）
- **生卒年 ↔ 朝代图层联动**：群体上地图按平均指数年（或众数朝代过半时的名称优先）、反查挖人按地名存续期，自动切换 CHGIS 朝代图层（年份→朝代键取"建立之年归新朝"规则：618→唐、907→五代、1127→南宋）

## 启动预热

- 模块级后台线程在启动时预建 CBDB 连接 + 装载反查坐标缓存（desktop.py 是 `from app import app` 同进程起服务，钩子必须在模块级，`__main__` 守卫在生产版不触发）
- 冷启动后首个 CBDB 查询原本要 ~79s（Access 打开 613MB mdb 冷文件），预热与用户点开窗口的操作重叠；失败静默降级为按需加载
- 坐标反查走 `_addr_coords()` 内存缓存（约 60k 条，threading.Lock 单飞双检），热查询 <0.5s

## 已知数据边界

- **亲属数据不全**：CBDB 亲属以自我为中心记录（如苏洵的 KIN_DATA 只有苏辙，没有苏轼）。查无记录是忠实呈现，不是 bug。
- **社会关系多未标年份**：年份区间过滤结果常骤减，属数据现实。
- **姻亲/外亲无五服**：KIN_Mourning 只收本宗血亲 159 键，妹夫/外甥等显示"—"。
- **性别过滤**：c_female 是 BIT 列，pyodbc 必须绑 bool（绑 int 会被 Access ODBC 静默置否）。
- **Access 参数上限**：IN 查询分批（CHUNK=500），大范围查询截断 1500 防溢出。
- **Access 函数不吃参数**：`SQR/COS` 内嵌 `?` 报"无效的过程调用"；坐标反查改为 SQL 曼哈顿粗排（ORDER BY 带参合法）+ Python 端精确距离。

## 项目结构

```
historia-server/
├── app.py                 # Flask 主应用（全部 API）
├── desktop.py             # 桌面启动器（pywebview）
├── JuneXi.spec            # PyInstaller one-dir 打包定义
├── start.bat              # 纯后端启动
├── requirements.txt
├── templates/index.html
├── static/
│   ├── css/style.css
│   └── js/                # app.js + data/（朝代/官名/地名/避讳等字典）
├── packaging/june-xi.iss  # Inno Setup 安装包脚本
├── tools/                 # 数据工具脚本
├── _test_phase1-8.py      # 回归测试（含 geojson 筛选与坐标反查）
└── _archive/              # 历史开发临时文件（不维护）
```

## 历史地理底图

- **高德**（默认，中文标注）：`webrd0{s}.is.autonavi.com`——Korm 网络下唯一稳定中文源
- **Esri Dark Gray**（英文备选）：`server.arcgisonline.com`
- OSM / GeoQ 在当前网络不可达；天地图需 API key

## 注意事项

- Obsidian 必须处于运行状态，Local REST API 插件必须启用
- 默认监听 `127.0.0.1` 动态端口，仅本地访问
- 安装版端口是动态的（desktop.py 自动找空闲端口）
- WebView2 窗口最小化时 PrintWindow 截不到图；pw=2 才能截 WebView2 内容
- OpenClaw 受管浏览器对 127.0.0.1 页面子资源缓存顽固，改前端后要加查询参数强制重载

---

*最后更新：2026-09-28（地图联动三连 + 坐标反查内存缓存 + 启动预热）*
