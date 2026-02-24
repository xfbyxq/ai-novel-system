import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Tabs, Spin, Breadcrumb, Card, Descriptions, Space, Typography, Button } from 'antd';
import { HomeOutlined, RobotOutlined } from '@ant-design/icons';
import type { Novel } from '@/api/types';
import { getNovel } from '@/api/novels';
import StatusBadge from '@/components/StatusBadge';
import AIChatDrawer from '@/components/AIChatDrawer';
import { formatWordCount, formatCost, formatDate } from '@/utils/format';
import OverviewTab from './OverviewTab';
import WorldSettingTab from './WorldSettingTab';
import CharactersTab from './CharactersTab';
import PlotOutlineTab from './PlotOutlineTab';
import ChaptersTab from './ChaptersTab';
import GenerationHistoryTab from './GenerationHistoryTab';

export default function NovelDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [novel, setNovel] = useState<Novel | null>(null);
  const [loading, setLoading] = useState(true);
  const [aiChatOpen, setAiChatOpen] = useState(false);
  const [currentTab, setCurrentTab] = useState('overview');

  const loadNovel = useCallback(async () => {
    if (!id) return;
    try {
      const data = await getNovel(id);
      setNovel(data);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { void loadNovel(); }, [loadNovel]);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!novel || !id) return <Typography.Text>小说不存在</Typography.Text>;

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          { title: <><HomeOutlined /> 首页</>, onClick: () => navigate('/') },
          { title: '小说管理', onClick: () => navigate('/novels') },
          { title: novel.title },
        ]}
      />

      <Card 
        style={{ marginBottom: 16 }}
        extra={
          <Button 
            type="primary" 
            icon={<RobotOutlined />}
            onClick={() => setAiChatOpen(true)}
          >
            AI助手
          </Button>
        }
      >
        <Descriptions column={{ xs: 1, sm: 2, md: 4 }}>
          <Descriptions.Item label="标题">
            <Typography.Text strong>{novel.title}</Typography.Text>
          </Descriptions.Item>
          <Descriptions.Item label="类型">{novel.genre}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <StatusBadge type="novel" status={novel.status} />
          </Descriptions.Item>
          <Descriptions.Item label="作者">{novel.author}</Descriptions.Item>
          <Descriptions.Item label="总字数">{formatWordCount(novel.word_count)}</Descriptions.Item>
          <Descriptions.Item label="章节数">{novel.chapter_count}</Descriptions.Item>
          <Descriptions.Item label="Token成本">{formatCost(novel.token_cost)}</Descriptions.Item>
          <Descriptions.Item label="创建时间">{formatDate(novel.created_at)}</Descriptions.Item>
        </Descriptions>
        {novel.tags && novel.tags.length > 0 && (
          <Space style={{ marginTop: 8 }}>
            <Typography.Text type="secondary">标签：</Typography.Text>
            {novel.tags.map((t) => (
              <Typography.Text key={t} code>{t}</Typography.Text>
            ))}
          </Space>
        )}
      </Card>

      <Tabs
        defaultActiveKey="overview"
        activeKey={currentTab}
        onChange={setCurrentTab}
        items={[
          { key: 'overview', label: '概览', children: <OverviewTab novel={novel} onRefresh={loadNovel} /> },
          { key: 'world', label: '世界观', children: <WorldSettingTab novelId={id} /> },
          { key: 'characters', label: '角色', children: <CharactersTab novelId={id} /> },
          { key: 'outline', label: '大纲', children: <PlotOutlineTab novelId={id} /> },
          { key: 'chapters', label: '章节', children: <ChaptersTab novelId={id} /> },
          { key: 'generation', label: '生成历史', children: <GenerationHistoryTab novelId={id} onNovelRefresh={loadNovel} /> },
        ]}
      />

      <AIChatDrawer
        open={aiChatOpen}
        onClose={() => setAiChatOpen(false)}
        scene="novel_revision"
        novelId={id}
      />
    </div>
  );
}
