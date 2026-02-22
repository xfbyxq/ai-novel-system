import { useEffect, useState } from 'react';
import { Row, Col, Typography, Table, Spin } from 'antd';
import {
  BookOutlined,
  FileTextOutlined,
  DollarOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import type { Novel, GenerationTask } from '@/api/types';
import { getNovels } from '@/api/novels';
import { getGenerationTasks } from '@/api/generation';
import StatsCard from '@/components/StatsCard';
import NovelCard from '@/components/NovelCard';
import StatusBadge from '@/components/StatusBadge';
import { formatCost, formatDate, formatWordCount } from '@/utils/format';

export default function Dashboard() {
  const [novels, setNovels] = useState<Novel[]>([]);
  const [runningTasks, setRunningTasks] = useState<GenerationTask[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [novelRes, taskRes] = await Promise.all([
          getNovels(1, 100),
          getGenerationTasks(undefined, 'running', 1, 50),
        ]);
        setNovels(novelRes.items);
        setRunningTasks(taskRes.items);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  const totalWords = novels.reduce((s, n) => s + n.word_count, 0);
  const totalCost = novels.reduce((s, n) => s + Number(n.token_cost || 0), 0);

  return (
    <div>
      <Typography.Title level={4}>仪表盘</Typography.Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}>
          <StatsCard title="小说总数" value={novels.length} icon={<BookOutlined />} color="#1890ff" />
        </Col>
        <Col xs={12} sm={6}>
          <StatsCard title="总字数" value={formatWordCount(totalWords)} icon={<FileTextOutlined />} color="#52c41a" />
        </Col>
        <Col xs={12} sm={6}>
          <StatsCard title="Token 成本" value={formatCost(totalCost)} icon={<DollarOutlined />} color="#faad14" />
        </Col>
        <Col xs={12} sm={6}>
          <StatsCard title="进行中任务" value={runningTasks.length} icon={<ThunderboltOutlined />} color="#722ed1" />
        </Col>
      </Row>

      <Typography.Title level={5}>最近小说</Typography.Title>
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {novels.slice(0, 6).map((novel) => (
          <Col xs={24} sm={12} md={8} key={novel.id}>
            <NovelCard novel={novel} />
          </Col>
        ))}
        {novels.length === 0 && (
          <Col span={24}>
            <Typography.Text type="secondary">暂无小说，去创建一个吧！</Typography.Text>
          </Col>
        )}
      </Row>

      {runningTasks.length > 0 && (
        <>
          <Typography.Title level={5}>进行中的任务</Typography.Title>
          <Table
            dataSource={runningTasks}
            rowKey="id"
            size="small"
            pagination={false}
            columns={[
              { title: '任务类型', dataIndex: 'task_type', render: (v: string) => v === 'planning' ? '企划' : '写作' },
              { title: '状态', dataIndex: 'status', render: (v: string) => <StatusBadge type="task" status={v} /> },
              { title: '开始时间', dataIndex: 'started_at', render: formatDate },
            ]}
          />
        </>
      )}
    </div>
  );
}
