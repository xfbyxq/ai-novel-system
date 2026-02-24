import { Card, Typography, Space } from 'antd';
import { useNavigate } from 'react-router-dom';
import type { Novel } from '@/api/types';
import StatusBadge from './StatusBadge';
import { formatWordCount, formatDate } from '@/utils/format';

interface Props {
  novel: Novel;
}

export default function NovelCard({ novel }: Props) {
  const navigate = useNavigate();
  return (
    <Card
      hoverable
      onClick={() => navigate(`/novels/${novel.id}`)}
      style={{ height: '100%' }}
    >
      <Space orientation="vertical" size={4} style={{ width: '100%' }}>
        <Space>
          <Typography.Text strong style={{ fontSize: 16 }}>
            {novel.title}
          </Typography.Text>
          <StatusBadge type="novel" status={novel.status} />
        </Space>
        <Typography.Text type="secondary">{novel.genre}</Typography.Text>
        <Space separator={<Typography.Text type="secondary">|</Typography.Text>}>
          <Typography.Text>{formatWordCount(novel.word_count)} 字</Typography.Text>
          <Typography.Text>{novel.chapter_count} 章</Typography.Text>
          <Typography.Text>{formatDate(novel.created_at)}</Typography.Text>
        </Space>
      </Space>
    </Card>
  );
}
