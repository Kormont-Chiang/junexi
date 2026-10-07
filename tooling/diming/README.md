# 地名大辞典结构化管线（tooling/diming）

《中国历史地名大辞典》（史为乐，中国社科 2005，3277 页扫描版）OCR → 结构化 → 端点数据。

## 流水线

```
diming_ocr.jsonl（v4 OCR 产物，references/toolbooks，不进库）
  └─ parse_diming.py        双栏解析+信号词切分+索引真值引导截断(v2) → diming_entries.jsonl
  └─ clean_diming.py        修正表+垃圾剔除+同词头去重 → diming_clean.jsonl（端点数据）
_idx_truth.json（idx_truth.py 从索引页抽 58,099 词头带印刷页码）
  └─ recall_v3.py           书眉锚定覆盖率折算召回测量
  └─ miss_attr.py           漏抽三级归因（OCR缺行/解析漏/未知）
```

## 运行

```bash
# 数据目录指向 references（OCR jsonl + 真值文件都在那里）
set DIMING_DATA=C:\...\references\toolbooks
python tooling/diming/parse_diming.py
python tooling/diming/recall_v3.py
python tooling/diming/clean_diming.py --full   # OCR 100% 后才写正式数据
```

## 关键设计

- **书眉双版式**：右页眉 `4二画二`（页码在前）、左页眉 `二画二丁7`（页码在尾），两种都解析
- **印刷页码≠pdf 页序**：全书有插页，全局偏移会漂移——一律以书眉为准
- **v2 索引真值引导截断**：词头过食（"二程墓为北宋…"）从长到短扫描、切点须命中
  索引词头真值；无真值文件时退回 v1 语义（精度优先）
- 当前召回 ~77%（2026-10-07，正文 OCR 约 1/3 时测）；剩余漏抽约 4 成是 v4 OCR 缺行，
  v6 重扫可望找回
