import { useEffect, useState, useCallback } from 'react';
import { Spin, Collapse, Typography, Descriptions, Tag, Empty } from 'antd';
import type { WorldSetting } from '@/api/types';
import { getWorldSetting } from '@/api/outlines';

interface Props {
  novelId: string;
}

function renderJsonField(data: unknown): React.ReactNode {
  if (!data) return <Typography.Text type="secondary">暂无数据</Typography.Text>;
  if (typeof data === 'string') return <Typography.Paragraph>{data}</Typography.Paragraph>;
  if (Array.isArray(data)) {
    if (data.length === 0) return <Typography.Text type="secondary">暂无</Typography.Text>;
    return (
      <div>
        {data.map((item, i) => (
          <div key={i} style={{ marginBottom: 8 }}>
            {typeof item === 'object' ? (
              <Descriptions bordered size="small" column={1}>
                {Object.entries(item as Record<string, unknown>).map(([k, v]) => (
                  <Descriptions.Item key={k} label={k}>
                    {typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v ?? '')}
                  </Descriptions.Item>
                ))}
              </Descriptions>
            ) : (
              <Tag>{String(item)}</Tag>
            )}
          </div>
        ))}
      </div>
    );
  }
  if (typeof data === 'object') {
    const entries = Object.entries(data as Record<string, unknown>);
    return (
      <Descriptions bordered size="small" column={1}>
        {entries.map(([k, v]) => (
          <Descriptions.Item key={k} label={k}>
            {typeof v === 'object' ? (
              <pre style={{ margin: 0, fontSize: 12, whiteSpace: 'pre-wrap' }}>
                {JSON.stringify(v, null, 2)}
              </pre>
            ) : String(v ?? '')}
          </Descriptions.Item>
        ))}
      </Descriptions>
    );
  }
  return String(data);
}

export default function WorldSettingTab({ novelId }: Props) {
  const [ws, setWs] = useState<WorldSetting | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const fetchWorldSetting = useCallback(async (nid: string) => {
    setLoading(true);
    try {
      const data = await getWorldSetting(nid);
      setWs(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchWorldSetting(novelId);
  }, [novelId, fetchWorldSetting]);

  if (loading) return <Spin />;
  if (error || !ws) return <Empty description="暂无世界观数据，请先执行企划" />;

  const sections = [
    { key: 'basic', label: '基本信息', children: (
      <Descriptions column={2}>
        <Descriptions.Item label="世界名称">{ws.world_name || '-'}</Descriptions.Item>
        <Descriptions.Item label="世界类型">{ws.world_type || '-'}</Descriptions.Item>
      </Descriptions>
    )},
    { key: 'power', label: '力量体系', children: renderJsonField(ws.power_system) },
    { key: 'geo', label: '地理设定', children: renderJsonField(ws.geography) },
    { key: 'factions', label: '势力组织', children: renderJsonField(ws.factions) },
    { key: 'rules', label: '世界规则', children: renderJsonField(ws.rules) },
    { key: 'timeline', label: '时间线', children: renderJsonField(ws.timeline) },
    { key: 'special', label: '特殊元素', children: renderJsonField(ws.special_elements) },
  ];

  return (
    <Collapse
      defaultActiveKey={['basic', 'power']}
      items={sections}
    />
  );
}
