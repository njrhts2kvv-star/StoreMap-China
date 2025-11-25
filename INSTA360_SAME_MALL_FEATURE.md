# DJI和Insta360门店同商场检查功能

## 功能说明

当确认门店的商场归属时，系统会自动检查是否有另一个品牌的门店在同一个商场，并在记忆文件中记录这个信息。

- **DJI门店**：检查是否有Insta360门店在同一商场
- **Insta360门店**：检查是否有DJI门店在同一商场

## 新增字段

在 `poi_memory.csv` 中新增了字段：
- `insta_is_same_mall_with_dji` - 标识 DJI 和 Insta360 门店是否在同一商场
  - `True` - DJI 和 Insta360 门店在同一商场（两个品牌都有门店）
  - `False` - 只有当前品牌的门店，没有另一个品牌的门店
  - 空字符串 - 未确认或非商场门店

## 工作流程

### 1. DJI门店处理
当确认DJI门店的商场后，系统会：
1. 检查同一城市中是否有Insta360门店使用相同的商场名称
2. 如果找到匹配的Insta360门店：
   - 自动标记当前DJI门店 `insta_is_same_mall_with_dji = "True"`
   - 同时更新匹配的Insta360门店记录 `insta_is_same_mall_with_dji = "True"`
   - 在终端显示匹配的Insta360门店列表
3. 如果没有找到匹配的Insta360门店，标记为 `insta_is_same_mall_with_dji = "False"`

### 2. Insta360门店处理
当确认Insta360门店的商场后，系统会：
1. 检查同一城市中是否有DJI门店使用相同的商场名称
2. 如果找到匹配的DJI门店：
   - 自动标记当前Insta360门店 `insta_is_same_mall_with_dji = "True"`
   - 同时更新匹配的DJI门店记录 `insta_is_same_mall_with_dji = "True"`
   - 在终端显示匹配的DJI门店列表
3. 如果没有找到匹配的DJI门店：
   - 系统会在终端显示提示信息
   - 询问用户是否确认不在同一商场
   - 用户输入 `y` 确认不在同一商场，或 `n` 需要重新确认

### 3. 终端显示示例

**情况1：DJI门店发现Insta360门店在同一商场**
```
[信息] DJI门店 '北京合生汇授权体验店' 与以下Insta360门店在同一商场:
  - 影石Insta360北京朝阳合生汇授权体验店
[自动] 标记为同一商场: True
```

**情况2：Insta360门店发现DJI门店在同一商场**
```
[信息] Insta360门店 '影石Insta360北京朝阳合生汇授权体验店' 与以下DJI门店在同一商场:
  - 北京合生汇授权体验店
[自动] 标记为同一商场: True
```

**情况3：未发现另一个品牌门店在同一商场（Insta360需要确认）**
```
--------------------------------------------------------------------------------
[进度: 5/100] Insta360门店商场确认
Insta360门店: 影石Insta360北京SKP授权体验店 | 城市: 市辖区
地址: 北京市朝阳区建国路87号北京SKPF5层D5297影石Insta360
确认的商场: 北京SKP

✗ 未发现DJI门店在同一商场

操作: y=确认不在同一商场 | n=需要重新确认 | q=退出
> y
[确认] 是否在同一商场: False
```

**情况4：DJI门店未发现Insta360门店在同一商场**
```
[信息] DJI门店 '北京SKP授权体验店' 未发现Insta360门店在同一商场
[自动] 标记为同一商场: False
```

## 记忆文件更新

- 所有DJI和Insta360门店的商场确认记录都会包含 `insta_is_same_mall_with_dji` 字段
- 如果记忆文件中已有记录但缺少该字段，系统会在处理时自动补充
- **双向更新**：当发现匹配时，两个品牌的门店记录都会同时更新

## 使用方法

运行 `interactive_mall_matcher.py` 时，系统会自动处理所有门店的同商场检查：

```bash
python interactive_mall_matcher.py
```

## 注意事项

1. **DJI和Insta360门店都会进行同商场检查**
2. 检查基于商场名称和城市进行匹配
3. 如果商场名称完全一致，会自动标记为同一商场
4. **双向标记**：如果DJI和Insta360在同一商场，两者的 `insta_is_same_mall_with_dji` 都会标记为 `True`
5. 如果未找到匹配：
   - DJI门店：自动标记为 `False`
   - Insta360门店：需要用户手动确认

## 相关函数

- `check_dji_stores_in_same_mall()` - 检查DJI是否有对应商场的门店
- `check_insta_stores_in_same_mall()` - 检查Insta360是否有对应商场的门店
- `prompt_same_mall_confirmation()` - 提示用户确认是否在同一商场（适用于DJI和Insta360）

## 字段含义

`insta_is_same_mall_with_dji` 字段标识 **DJI 和 Insta360 门店是否在同一商场**：

- **字段含义**：标识当前门店所在的商场是否有另一个品牌（DJI 或 Insta360）的门店
- **对于DJI门店**：标识是否有 Insta360 门店在同一商场
- **对于Insta360门店**：标识是否有 DJI 门店在同一商场
- **双向标记**：如果 DJI 和 Insta360 在同一商场，两者的 `insta_is_same_mall_with_dji` 都会标记为 `True`
- **值说明**：
  - `True`：DJI 和 Insta360 门店在同一商场（两个品牌都有门店）
  - `False`：只有当前品牌的门店，没有另一个品牌的门店
  - 空字符串：未确认或非商场门店

