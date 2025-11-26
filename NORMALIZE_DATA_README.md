# 数据标准化处理任务说明

## 概述

本脚本用于对门店和商场数据进行标准化清洗，核心原则是：
1. **完全尊重并保留** `all_stores_final.csv` 中已经确立的"门店-商场"关联关系
2. **仅对已知商场**的信息（名称、坐标）进行高德 POI 标准化清洗
3. **绝不为没有关联商场的门店**（如街边店）新增匹配

## 前置要求

1. Python 3.8+
2. 安装依赖：
   ```bash
   pip install pandas requests geopy rapidfuzz
   ```
3. 配置高德地图 API Key：
   - 设置环境变量 `AMAP_WEB_KEY`，或
   - 在 `.env.local` 文件中设置 `AMAP_WEB_KEY=your_key`

## 输入文件

- `all_stores_final.csv`: 主数据表，包含门店信息和已确认的商场名称（`mall_name` 字段）
- `poi_memory.csv`: （可选）记忆库，包含历史确认过的商场 POI 信息

## 执行步骤

脚本按以下步骤执行：

### Step 1: 门店数据初始化
- 读取 `all_stores_final.csv`
- 创建 `Store_Master` DataFrame
- **继承关联关系**：直接保留原表中的 `mall_name` 字段
- **清洗门店坐标**：调用高德地理编码 API，更新 `corrected_lat` 和 `corrected_lng`

### Step 2: 商场白名单提取
- 从 `Store_Master` 中提取所有**非空**的商场名称
- 去重，生成待清洗商场清单
- 为每个商场收集关联门店的坐标信息（用于后续 API 搜索）

### Step 3: 商场 POI 标准化

对每个商场按优先级处理：

**Priority A: 查阅记忆库**
- 如果在 `poi_memory.csv` 中存在且已标记为 `is_manual_confirmed=True`
- 直接复用其 `amap_poi_id`、标准名称、`mall_lat`、`mall_lng`

**Priority B: API 定向验证**
- 如果记忆库中没有，则使用属于该商场的任意一家门店的坐标作为 `location` 参数
- 调用高德关键字搜索 API（Text Search）
- 验证逻辑：
  - 找到距离门店最近（< 500m）且名称相似度高的唯一最佳 POI
  - 获取该 POI 的官方名称和官方中心点坐标

### Step 4: 数据回填与输出

生成以下文件：

1. **Store_Master_Cleaned.csv**
   - 包含精确门店坐标和标准化的 `mall_id`
   - 字段：`store_id`, `brand`, `name`, `address`, `city`, `province`, `corrected_lat`, `corrected_lng`, `mall_name`, `mall_id`

2. **Mall_Master_Cleaned.csv**
   - 仅包含清洗后的商场主数据
   - 字段：`mall_id`, `mall_name`, `original_name`, `mall_lat`, `mall_lng`, `amap_poi_id`, `city`, `source`, `store_count`

3. **Mall_Unmatched_Log.csv**（如果存在未匹配的商场）
   - 记录那些在 API 中搜索不到或差异过大无法自动确认的商场
   - 供人工检查

## 使用方法

```bash
python normalize_store_mall_data.py
```

## 关键限制

- ✅ **Do Not Match New**: 禁止对原数据中没有商场的门店运行"周边搜索"来强行匹配商场
- ✅ **Verify Only**: API 仅用于验证和修正现有商场的元数据（名称/坐标）

## 输出说明

### Store_Master_Cleaned.csv
- `store_id`: 门店唯一标识（来自 `uuid`）
- `corrected_lat` / `corrected_lng`: 清洗后的门店坐标
- `mall_id`: 标准化的商场ID（如果门店关联了商场）

### Mall_Master_Cleaned.csv
- `mall_id`: 生成的唯一商场ID
- `mall_name`: 清洗后的官方名称（来自高德 POI）
- `original_name`: 清洗前的原始名称
- `mall_lat` / `mall_lng`: 商场的标准坐标
- `amap_poi_id`: 高德 POI ID
- `source`: 数据来源（`memory` / `api` / `unmatched`）

### Mall_Unmatched_Log.csv
- `mall_name`: 未匹配的商场名称
- `city`: 城市
- `reason`: 未匹配的原因
- `reference_lat` / `reference_lng`: 参考坐标

## 注意事项

1. API 调用有频率限制，脚本已内置延迟（0.2-0.3秒）
2. 如果地理编码失败，将保留原始坐标
3. 如果记忆库中没有匹配，将尝试 API 搜索
4. 如果 API 搜索也失败，将记录到 `Mall_Unmatched_Log.csv` 供人工处理

## 示例输出

```
============================================================
数据标准化处理任务
============================================================

读取输入文件: all_stores_final.csv
  门店总数: 1253

读取记忆库: poi_memory.csv
  记忆记录数: 1234

=== Step 1: 门店数据初始化 ===
  处理进度: 50/1253
  处理进度: 100/1253
  ...
  完成！已更新 1200/1253 个门店坐标

=== Step 2: 商场白名单提取 ===
  找到 450 个待清洗的商场

=== Step 3: 商场POI标准化 ===
[1/450] 处理商场: 天河百脑汇 (广州市)
  ✓ 从记忆库获取: 天河百脑汇 (23.126039, 113.338246)
...

  完成！
  - 成功标准化: 445 个
  - 未匹配: 5 个

=== Step 4: 数据回填与输出 ===
  保存文件...
  ✓ Store_Master_Cleaned.csv
  ✓ Mall_Master_Cleaned.csv
  ✓ Mall_Unmatched_Log.csv (5 条记录)

=== 完成 ===
  门店总数: 1253
  商场总数: 450
  已标准化商场: 445
  未匹配商场: 5
```

