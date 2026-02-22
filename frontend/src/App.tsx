import { RouterProvider } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import router from './router';
import ErrorBoundary from './components/ErrorBoundary';

export default function App() {
  return (
    <ErrorBoundary>
      <ConfigProvider locale={zhCN}>
        <RouterProvider router={router} />
      </ConfigProvider>
    </ErrorBoundary>
  );
}
