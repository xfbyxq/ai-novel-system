---
trigger: code_generation,code_modification
---

# 前端代码规范

## TypeScript编码规范

### 命名规范
- **组件/类**: 帕斯卡命名法 (PascalCase)
- **函数/变量**: 驼峰命名法 (camelCase)
- **常量**: 全大写蛇形命名 (UPPER_SNAKE_CASE)
- **文件命名**: 短横线命名法 (kebab-case.tsx)
- **组件目录**: 帕斯卡命名法 (Button/)

### 目录结构规范
```
src/
├── components/        # 通用组件
│   ├── Button/
│   │   ├── index.tsx
│   │   ├── index.less
│   │   └── index.test.tsx
├── pages/             # 页面组件
├── hooks/             # 自定义Hooks
├── services/          # API服务
├── stores/            # Zustand状态管理
├── utils/             # 工具函数
├── types/             # 类型定义
└── assets/            # 静态资源
```

### 组件设计规范
- 使用函数组件 + Hooks
- 组件必须使用TypeScript类型定义
- Props必须定义接口类型
- 大组件必须进行拆分

```typescript
// 正确示例
interface ButtonProps {
  /** 按钮文字 */
  children: React.ReactNode;
  /** 按钮类型 */
  type?: 'primary' | 'default' | 'dashed';
  /** 点击回调 */
  onClick?: () => void;
  /** 是否加载中 */
  loading?: boolean;
  /** 自定义类名 */
  className?: string;
}

/**
 * 通用按钮组件
 * 用于页面中的各种操作按钮
 */
export const Button: FC<ButtonProps> = ({
  children,
  type = 'default',
  onClick,
  loading = false,
  className,
}) => {
  return (
    <AntButton
      type={type}
      onClick={onClick}
      loading={loading}
      className={className}
    >
      {children}
    </AntButton>
  );
};
```

### 状态管理规范 (Zustand)

```typescript
// 创建Store
import { create } from 'zustand';

interface UserState {
  user: User | null;
  isLoading: boolean;
  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  fetchUser: () => Promise<void>;
}

export const useUserStore = create<UserState>((set) => ({
  user: null,
  isLoading: false,
  setUser: (user) => set({ user }),
  setLoading: (isLoading) => set({ isLoading }),
  fetchUser: async () => {
    set({ isLoading: true });
    try {
      const user = await userService.getCurrentUser();
      set({ user });
    } catch (error) {
      console.error('获取用户失败:', error);
    } finally {
      set({ isLoading: false });
    }
  },
}));
```

### API服务规范

```typescript
// 使用Axios创建API客户端
import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 10000,
});

// 请求拦截器 - 添加认证Token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器 - 统一错误处理
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      // 处理未授权
      router.push('/login');
    }
    return Promise.reject(error);
  }
);
```

### 样式规范
- 组件样式使用CSS Modules或less
- 避免全局样式污染
- 统一使用Ant Design的主题配置

### UI组件使用规范
- 优先使用Ant Design组件
- 自定义组件必须遵循Ant Design的设计模式
- 保持界面风格一致性

### 性能优化
- 使用React.memo包装纯展示组件
- 合理使用useMemo和useCallback
- 图片资源使用懒加载
- 列表渲染使用虚拟滚动