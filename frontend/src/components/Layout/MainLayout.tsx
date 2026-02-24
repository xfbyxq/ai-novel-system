import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, theme, Typography } from 'antd';
import {
  DashboardOutlined,
  BookOutlined,
  CloudDownloadOutlined,
  LineChartOutlined,
  UserOutlined,
  SendOutlined,
  MonitorOutlined,
} from '@ant-design/icons';

const { Sider, Content, Header } = Layout;

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/novels', icon: <BookOutlined />, label: '小说管理' },
  { key: '/crawler', icon: <CloudDownloadOutlined />, label: '爬虫任务' },
  { key: '/market-data', icon: <LineChartOutlined />, label: '市场数据' },
  { key: '/accounts', icon: <UserOutlined />, label: '平台账号' },
  { key: '/publish', icon: <SendOutlined />, label: '发布管理' },
  { key: '/monitoring', icon: <MonitorOutlined />, label: '系统监控' },
];

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = theme.useToken();

  const selectedKey = location.pathname === '/' ? '/' : '/' + location.pathname.split('/')[1];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
      >
        <div
          style={{
            height: 48,
            margin: 12,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Typography.Text
            strong
            style={{ color: '#fff', fontSize: collapsed ? 14 : 16, whiteSpace: 'nowrap' }}
          >
            {collapsed ? 'AI' : 'AI 小说系统'}
          </Typography.Text>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            padding: '0 24px',
            background: token.colorBgContainer,
            display: 'flex',
            alignItems: 'center',
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
          }}
        >
          <Typography.Title level={4} style={{ margin: 0 }}>
            AI 小说生成系统
          </Typography.Title>
        </Header>
        <Content style={{ margin: 16 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
