# FRONTEND 模块

**TypeScript/React前端**: SPA应用，Vite构建

## OVERVIEW

React 18 + TypeScript + Vite构建的小说系统前端，Ant Design组件库。

## STRUCTURE

```
frontend/src/
├── api/          # API客户端
├── components/  # React组件
├── hooks/       # 自定义Hooks
├── pages/       # 页面组件
├── stores/      # Zustand状态管理
├── types/       # TypeScript类型
└── utils/       # 工具函数
```

## WHERE TO LOOK

| 任务 | 路径 |
|------|------|
| 新增页面 | `pages/` |
| 组件库 | `components/` |
| API调用 | `api/` |
| 状态管理 | `stores/` |
| 路由配置 | `router.tsx` |

## COMMANDS

```bash
cd frontend
npm install
npm run dev      # 开发服务器 (端口3000)
npm run build   # 生产构建
npm run preview # 预览构建
```

## CONVENTIONS

- **组件**: 函数组件 + hooks
- **状态**: Zustand状态管理
- **API**: Axios客户端
- **样式**: CSS Modules / Ant Design
- **类型**: 严格TypeScript，无any

## API PATTERN

```typescript
import api from '@/utils/api'

// GET请求
const novels = await api.get('/api/v1/novels')

// POST请求
await api.post('/api/v1/novels', { title: '新小说' })
```
