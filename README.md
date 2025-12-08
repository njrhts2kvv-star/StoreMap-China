# 门店分布对比

DJI vs Insta360 全国门店数据可视化

## 环境变量配置

### 本地开发

1. 复制 `.env.example` 为 `.env.local`
2. 在 `.env.local` 中设置你的高德地图 API Key：

```env
VITE_AMAP_KEY=your_amap_key_here
```

### Vercel 部署

在 Vercel 项目设置中添加环境变量：

1. 进入 Vercel 项目 Dashboard
2. 点击 **Settings** → **Environment Variables**
3. 添加新的环境变量：
   - **Name**: `VITE_AMAP_KEY`
   - **Value**: 你的高德地图 API Key
   - **Environment**: Production, Preview, Development（根据需要选择）
4. 重新部署项目

### 备选方案：代码中直接设置（不推荐）

如果无法使用环境变量，可以在 `src/config/amap.ts` 中的 `HARDCODED_KEY` 变量直接设置 key。

**注意**：这种方式会将 key 暴露在代码中，存在安全风险，仅作为临时方案。

## 开发

```bash
npm install
npm run dev
```

## 构建

```bash
npm run build
```

---

## 新增：分析 / 截图工具（FastAPI + React）

### 后端（FastAPI + PostgreSQL）

1. 设置环境变量（可在仓库根目录创建 `.env`）：

```
DATABASE_URL=postgresql+psycopg2://user:password@host:5432/dbname
```

2. 安装依赖并启动：

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --app-dir .
```

接口基于 `/api` 前缀，健康检查：`GET /api/health`。

### 前端（React + Vite + Ant Design）

1. 设置环境变量（可选，默认指向本地后端 `http://localhost:8000/api`）：

```
VITE_API_BASE_URL=http://localhost:8000/api
```

2. 安装依赖并启动：

```bash
cd frontend
npm install
npm run dev
```

### 示例请求

```bash
curl http://localhost:8000/api/cities
curl http://localhost:8000/api/malls/1
curl "http://localhost:8000/api/brands/1/stores?city_code=310000"
```

前端主要页面：
- `/cities`：城市列表与商场、品牌结构
- `/cities/{city_code}`：城市下商场列表
- `/malls/{mall_id}`：商场详情与品牌矩阵
- `/brands`：品牌列表（按品类、tier 筛选）
- `/brands/{brand_id}`：品牌详情与门店列表
