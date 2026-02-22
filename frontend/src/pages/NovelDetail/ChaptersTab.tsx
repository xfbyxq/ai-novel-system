import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Table, Tag } from 'antd';
import type { Chapter } from '@/api/types';
import { getChapters } from '@/api/chapters';
import StatusBadge from '@/components/StatusBadge';
import { formatWordCount, formatDate } from '@/utils/format';

interface Props {
  novelId: string;
}

export default function ChaptersTab({ novelId }: Props) {
  const navigate = useNavigate();
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getChapters(novelId, page, 20);
      setChapters(res.items);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  }, [novelId, page]);

  useEffect(() => { load(); }, [load]);

  return (
    <Table
      dataSource={chapters}
      rowKey="id"
      loading={loading}
      pagination={{ current: page, pageSize: 20, total, onChange: setPage }}
      columns={[
        { title: '章节', dataIndex: 'chapter_number', width: 70, render: (v: number) => `第 ${v} 章` },
        { title: '卷', dataIndex: 'volume_number', width: 60 },
        {
          title: '标题', dataIndex: 'title', render: (v: string, r: Chapter) => (
            <a onClick={() => navigate(`/novels/${novelId}/chapters/${r.chapter_number}`)}>{v || '(未命名)'}</a>
          ),
        },
        { title: '字数', dataIndex: 'word_count', width: 80, render: formatWordCount },
        {
          title: '质量', dataIndex: 'quality_score', width: 80,
          render: (v: number | null) => v != null ? <Tag color={v >= 8 ? 'green' : v >= 6 ? 'orange' : 'red'}>{v}</Tag> : '-',
        },
        { title: '状态', dataIndex: 'status', width: 90, render: (v: string) => <StatusBadge type="chapter" status={v} /> },
        { title: '创建时间', dataIndex: 'created_at', width: 160, render: formatDate },
      ]}
    />
  );
}
