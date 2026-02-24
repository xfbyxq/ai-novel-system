import { createBrowserRouter } from 'react-router-dom';
import MainLayout from '@/components/Layout/MainLayout';
import Dashboard from '@/pages/Dashboard';
import NovelList from '@/pages/NovelList';
import NovelDetail from '@/pages/NovelDetail/NovelDetail';
import ChapterReader from '@/pages/ChapterReader';
import PlatformAccounts from '@/pages/PlatformAccounts';
import PublishTasks from '@/pages/PublishTasks';
import SystemMonitoring from '@/pages/SystemMonitoring';
import NotFound from '@/pages/NotFound';

const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'novels', element: <NovelList /> },
      { path: 'novels/:id', element: <NovelDetail /> },
      { path: 'novels/:id/chapters/:number', element: <ChapterReader /> },
      { path: 'accounts', element: <PlatformAccounts /> },
      { path: 'publish', element: <PublishTasks /> },
      { path: 'monitoring', element: <SystemMonitoring /> },
      { path: '*', element: <NotFound /> },
    ],
  },
]);

export default router;
