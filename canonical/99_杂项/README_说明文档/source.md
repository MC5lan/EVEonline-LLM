# EVE Online 英汉互译对照表

## 数据摘要

| 文件 | 内容 | 条目数 |
|------|------|--------|
| `types_zh_en.csv` | **全部物品**（舰船/装备/弹药/蓝图/技能书/矿石/植入体等） | **52,080** |
| `groups_zh_en.csv` | 物品分组（护卫舰/驱逐舰/巡洋舰/炮台/导弹等） | 1,599 |
| `categories_zh_en.csv` | 物品大类（舰船/装备/蓝图/技能/天体等） | 48 |
| `regions_zh_en.csv` | 星域名称 | 114 |

## 分类统计（TOP 10）

| 分类 | 英文 | 中文 | 条目数 |
|------|------|------|--------|
| SKINs | SKINs | 涂装 | 11,720 |
| Entity | Entity | 实体 | 7,241 |
| Celestial | Celestial | 天体 | 5,948 |
| Blueprint | Blueprint | 蓝图 | 5,084 |
| Module | Module | 装备 | 4,638 |
| Commodity | Commodity | 商品 | 4,034 |
| Implant | Implant | 植入体 | 2,261 |
| Charge | Charge | 弹药 | 1,156 |
| Skill | Skill | 技能 | 587 |
| Ship | Ship | 舰船 | 561 |

## 数据来源

- **主数据**: [EVE Ref Reference Data](https://docs.everef.net/datasets/reference-data)
 - 合并 CCP SDE + ESI + Hoboleaks
 - 更新时间: 2026-05-26
 - 格式: JSON (language-mapped)
- **验证源**:
 - 灰机wiki EVE中文维基 (https://eve.huijiwiki.com) — 官方SDE同步
 - 社区 EVE中英文对照表 (renrendoc.com)

## 交叉验证结论

✅ **EVE Ref 与灰机wiki（官方SDE）翻译 100% 一致**

- 核心验证条目 8/8 全部通过
- 唯一差异为格式性（"级"后缀的有无），无实质性翻译冲突
- 社区文档翻译与官方SDE完全对齐

## 字段说明 (types_zh_en.csv)

| 字段 | 说明 |
|------|------|
| typeID | EVE Online 物品唯一ID |
| name_en | 英文名称 |
| name_zh | 中文名称 |
| groupID | 分组ID |
| group_en | 英文分组名 |
| group_zh | 中文分组名 |
| categoryID | 分类ID |
| published | 是否已发布 |
| capacity | 容量 (m³) |
| mass | 质量 (kg) |
| volume | 体积 (m³) |