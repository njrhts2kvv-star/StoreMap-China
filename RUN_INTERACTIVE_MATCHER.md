# 门店商场匹配脚本运行指南

## 📋 前置要求

### 1. Python 环境
确保已安装 Python 3.7+：

```bash
python3 --version
```

### 2. 安装依赖包

```bash
pip install pandas requests geopy rapidfuzz
```

或者使用 requirements.txt（如果存在）：

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

脚本需要以下环境变量：

#### 必需：高德地图 API Key
- **变量名**: `AMAP_WEB_KEY`
- **获取方式**: 访问 [高德开放平台](https://lbs.amap.com/) 注册并创建 Web 服务 Key

#### 可选：LLM API Key（用于智能匹配）
- **变量名**: `BAILIAN_API_KEY`
- **获取方式**: 阿里云百炼平台 API Key
- **Base URL**: `BAILIAN_BASE_URL`（默认：`https://dashscope.aliyuncs.com/compatible-mode/v1`）

### 4. 配置方式

#### 方式一：创建 `.env.local` 文件（推荐）

在项目根目录创建 `.env.local` 文件：

```env
AMAP_WEB_KEY=你的高德API密钥
BAILIAN_API_KEY=你的百炼API密钥（可选）
BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

#### 方式二：直接设置环境变量

**macOS/Linux:**
```bash
export AMAP_WEB_KEY="你的高德API密钥"
export BAILIAN_API_KEY="你的百炼API密钥"  # 可选
```

**Windows (PowerShell):**
```powershell
$env:AMAP_WEB_KEY="你的高德API密钥"
$env:BAILIAN_API_KEY="你的百炼API密钥"  # 可选
```

## 🚀 运行脚本

### 基本运行

```bash
python3 interactive_mall_matcher.py
```

### 运行流程说明

1. **数据加载**: 脚本会自动读取 `dji_offline_stores.csv` 和 `insta360_offline_stores.csv`
2. **记忆检查**: 已处理过的门店会从 `poi_memory.csv` 中读取，跳过重复处理
3. **精准定位**: 对每个门店，先通过名称搜索获取高德精准坐标
4. **周边搜索**: 使用精准坐标搜索周边200米内的商场（或降级使用500米）
5. **智能匹配**: 
   - 优先使用自动匹配
   - 如果配置了 LLM，会使用 LLM 智能判断
   - 无法自动匹配时，会提示用户手动选择

### 交互式操作

当需要人工确认时，会显示：

```
[进度: 1/100] 需要确认
门店: DJI | 广州索盟百脑汇照材店 | 城市: 广州市
地址: 广州市天河区天河路598号百脑汇科技大厦一楼1D02铺
候选列表:
  1: 百脑汇科技大厦 [父POI] (距离 0m)
  2: 天汇广场 (距离 150m)
操作: 输入编号选择 | 0=非商场 | 直接输入=自定义名称 | q=退出 | x=扩大到5km
> 
```

**操作说明：**
- 输入数字：选择对应的候选商场
- 输入 `0`：标记为非商场门店
- 直接输入文字：自定义商场名称
- 输入 `q`：退出并保存当前进度
- 输入 `x`：扩大搜索范围到5公里（如果允许）

## 📁 输出文件

- **`all_stores_final.csv`**: 最终匹配结果，包含 `mall_name` 字段
- **`poi_memory.csv`**: 处理记忆文件，记录已匹配的门店（用于断点续传）

## 🔍 调试信息

脚本运行时会输出详细的调试信息：

```
[定位] 通过名称搜索获取精准坐标: (23.126039, 113.338246)
[定位] 发现父POI/商圈: 百脑汇科技大厦
[周边] 搜索半径 200m，找到 3 个候选
[候选] 将父POI '百脑汇科技大厦' 加入候选列表首位
[自动] 广州索盟百脑汇照材店 -> 百脑汇科技大厦
```

## ⚠️ 注意事项

1. **API 配额**: 注意高德地图 API 的调用次数限制
2. **坐标系**: 脚本会自动使用高德返回的 GCJ-02 坐标系，无需手动转换
3. **断点续传**: 已处理的记录会保存在 `poi_memory.csv`，重新运行时会跳过
4. **数据文件**: 确保 `dji_offline_stores.csv` 和 `insta360_offline_stores.csv` 存在且格式正确

## 🐛 常见问题

### Q: 提示 "请先在环境变量 AMAP_WEB_KEY 中配置高德 Web API Key"
**A**: 检查 `.env.local` 文件是否存在且格式正确，或直接设置环境变量。

### Q: 提示找不到数据文件
**A**: 确保 `dji_offline_stores.csv` 和 `insta360_offline_stores.csv` 在项目根目录。

### Q: 导入模块失败
**A**: 运行 `pip install pandas requests geopy rapidfuzz` 安装依赖。

### Q: API 调用失败
**A**: 检查 API Key 是否正确，以及是否有足够的调用配额。

