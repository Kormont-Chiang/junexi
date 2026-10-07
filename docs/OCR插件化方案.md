# JuneXi OCR 插件化方案

> 状态：方案 + 实测数据（2026-10-07）。Provider 协议与"灵眸"本地插件骨架待下轮落地。
> 目标：让工具书 OCR 管线（以及未来的任意"丢图出字"功能）可以像换墨盒一样换 OCR 引擎。

## 1. 需求与背景

- 工具书管线现状：核心内置 `rapidocr_onnxruntime`（PP-OCRv4 ONNX），地名大辞典全书 OCR 中。
- 实测痛点：v4 在扫描辞典页上会**丢生僻字**（"千人幢→千人""阎王碥→阎王""古搦岭→古岭"），词条名与释义粘连。
- 需求分层：本地离线（隐私/零成本，默认）＋ 云端高精度选配（用户自备 key，啃最难的页）。

## 2. Provider 协议（插件契约）

OCR 能力以**插件能力声明**方式接入现有插件系统：

```jsonc
// manifest.json 增量字段
{
  "id": "lingmu-ocr",
  "capabilities": ["ocr"],          // 声明本插件提供 OCR
  "ocr": {
    "priority": 100,                // 多 provider 并存时的选用优先级（大者优先）
    "local": true,                  // 是否本地推理（false = 云端，需用户配置 key）
    "models_bundled": false         // 模型是否随插件包（否=首启自 HuggingFace/模型仓下载）
  }
}
```

插件模块约定：包内 `__init__.py` 暴露

```python
def ocr_page(image_path: str) -> list[dict]:
    """返回 [{box:[x0,y0,x1,y1], text:str, conf:float}, ...]；失败抛异常由核心兜底。"""
```

- 核心侧 `ocr_runner`：扫描已启用插件的 `capabilities` 含 `ocr` 者 → 按 priority 取第一个可用 → 调用 `ocr_page`；异常或缺失 → 回落内置 v4。
- **JSONL 落盘 schema 与现管线一致**（{page, lines:[{box, text, conf}]}），解析器（_parse_diming 等）零改动。

## 3. 选型矩阵（2026-10-07 实测 + 官方基准）

| Provider | 引擎 | 离线 | 成本 | 实测表现（地名辞典页500） | 定位 |
|---|---|---|---|---|---|
| 内置 v4 | rapidocr_onnxruntime + PP-OCRv4 | ✅ | 0 | 丢字：幢/碥/搦；词条与释义粘连 | 兜底，存量不动 |
| **灵眸（推荐本地）** | rapidocr ≥3.x + **PP-OCRv6** small | ✅ | 0 | **全部找回**，且词条/释义间自动加空格（白送的分词信号） | 官方选配插件 |
| v5-server | rapidocr + PP-OCRv5 server_rec（繁体 93.29%） | ✅ | 0 | 未测；模型 ~81MB，繁体场景官方最强 | v6 遇挫时的备选 |
| 云端高精度 | 百度通用文字识别（高精度含位置版），繁体模式 | ❌ | 按量（约 ¥0.02/千次起） | 未接入；古籍/刻本场景口碑最佳 | ✅ `plugins/baidu-ocr`，用户自备 key |

实测记录（同页同 dpi=200，v6 引擎输出含 box 可排序）：
- v4：`千仙镇金时泗州…` / v6：`千仙镇 金时泗州平山镇之讹。`（空格分离词头）
- v4：`千人、百尺峡、胡孙愁、阎王、老君犁沟` / v6：`千人幢、百尺峡、胡孙愁、阎王碥、老君犁沟`
- v4：`即古岭也` / v6：`即古搦岭也`
- 耗时：v6 small 15-18s/页（与后台 v4 并行抢 CPU 时），solo 预计 8-12s/页

## 4. 隐私 / 成本 / 精度三轴

- 默认走本地（v4 兜底 → 装了灵眸走 v6）：零外发，零费用。
- 云端 provider 只在用户显式启用 + 填 key 后生效；调用前弹确认，JSONL 存本地。
- 学术场景建议：**普通工具书本地 v6 足够**；刻本/写本/虫蛀页再点云端。

## 5. 落地路线（2026-10-07 全部完成 ✅）

1. ✅ 核心侧 `ocr_service`（capability 发现 + priority + 兜底）+ 灵眸插件（PP-OCRv6）
2. ✅ 工具书管线 `_ocr_toolbook.py` 走 `ocr_service` 调度
3. ⏳ 官制大辞典 / 史讳辞典（等 Korm 重下完）**用 v6 起跑**——不再回填 v4 的坑
4. ✅ 地名大辞典：现有 v4 全书数据**保留**（全书一致性），v6 数据待全书重印时生成
5. ✅ 云端 provider（百度）插件落地：`plugins/baidu-ocr`，priority 50 排在灵眸之后；未配置 key 或调用失败自动回落本地；key 存用户数据目录不入库

配套：灵眸前端面板（👁️ 灵眸OCR tab：拖图识别+行级置信度）、独立页面通道 `/plugin/<id>/page` 首个真实用户、插件模板仓库 [jx-plugin-template](https://github.com/Kormont-Chiang/jx-plugin-template)。

## 6. 风险

- v6 引擎输出行序与 v4 不同（引擎内部排序策略变），解析器必须按 box 坐标重排（已确认 res.boxes 可取，左栏优先规则不变）
- v6 模型 small 版对极小字号脚注可能不如 server 版——如出现，灵眸插件内提供"模型档位"设置（small/server 二选一，server 首启多下 ~80MB）
- 百度 API 需要公网 + 实名认证 key；插件文档须写清免费额度与计费
