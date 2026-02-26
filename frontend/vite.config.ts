import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig(({ mode }) => {
  // 加载环境变量（只用于服务器端配置）
  const env = loadEnv(mode, process.cwd(), '')
  const apiProxyTarget = env.API_PROXY_TARGET || process.env.API_PROXY_TARGET || 'http://localhost:8000'
  
  console.log('🔍 Vite Proxy Target:', apiProxyTarget)
  
  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
      },
    },
    server: {
      host: '0.0.0.0',  // 监听所有网络接口，允许容器外部访问
      port: 3000,
      strictPort: true,
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
          secure: false,  // 如果目标是 https，可能需要设置为 false
          configure: (proxy, _options) => {
            proxy.on('error', (err, _req, _res) => {
              console.log('❌ Proxy error:', err);
            });
            proxy.on('proxyReq', (proxyReq, req, _res) => {
              console.log('→ Proxying:', req.method, req.url, '→', apiProxyTarget + req.url);
            });
            proxy.on('proxyRes', (proxyRes, req, _res) => {
              console.log('← Proxy response:', req.url, '→', proxyRes.statusCode);
            });
          },
        },
      },
    },
  }
})
