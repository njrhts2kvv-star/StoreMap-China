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
