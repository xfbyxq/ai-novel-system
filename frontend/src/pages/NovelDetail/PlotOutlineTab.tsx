import { useEffect, useState, useCallback } from 'react';
import { Spin, Empty, Tree, Card, Typography, Descriptions, Button } from 'antd';
import { RocketOutlined } from '@ant-design/icons';
import type { PlotOutline } from '@/api/types';
import { getPlotOutline } from '@/api/outlines';

interface Props {
  novelId: string;
}

interface VolumeItem {
  volume_num?: number;
  title?: string;
  summary?: string;
  chapters?: unknown[];
  key_events?: string[];
  [key: string]: unknown;
}

export default function PlotOutlineTab({ novelId }: Props) {
  const [outline, setOutline] = useState<PlotOutline | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const fetchOutline = useCallback(async (nid: string) => {
    setLoading(true);
    try {
      const data = await getPlotOutline(nid);
      setOutline(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchOutline(novelId);
  }, [novelId, fetchOutline]);

  if (loading) return <Spin />;
  if (error || !outline) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          <div>
            <Typography.Title level={5} style={{ marginBottom: 8 }}>大纲尚未生成</Typography.Title>
            <Typography.Text type="secondary">
              点击下方按钮前往「概览」标签页，启动企划任务后自动生成大纲
            </Typography.Text>
          </div>
        }
      >
        <Button type="primary" icon={<RocketOutlined />} onClick={() => {
          const overviewTab = document.querySelector('[data-node-key="overview"]') as HTMLElement;
          overviewTab?.click();
        }}>
          前往开始企划
        </Button>
      </Empty>
    );
  }

  const volumes = (outline.volumes || []) as VolumeItem[];

  const treeData = volumes.map((vol, i) => ({
    key: `vol-${i}`,
    title: `第 ${vol.volume_num || i + 1} 卷：${vol.title || '未命名'}`,
    children: [
      ...(vol.summary ? [{ key: `vol-${i}-summary`, title: `概要：${vol.summary}`, isLeaf: true }] : []),
      ...(vol.key_events || []).map((evt: string, j: number) => ({
        key: `vol-${i}-evt-${j}`,
        title: `事件：${evt}`,
        isLeaf: true,
      })),
    ],
  }));

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Descriptions column={2}>
          <Descriptions.Item label="结构类型">{outline.structure_type || '-'}</Descriptions.Item>
          <Descriptions.Item label="高潮章节">{outline.climax_chapter ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="卷数">{volumes.length}</Descriptions.Item>
        </Descriptions>
      </Card>

      {outline.main_plot && Object.keys(outline.main_plot).length > 0 && (
        <Card title="主线剧情" size="small" style={{ marginBottom: 16 }}>
          <Descriptions column={1} size="small" bordered>
            {Object.entries(outline.main_plot).map(([k, v]) => (
              <Descriptions.Item key={k} label={k}>
                {typeof v === 'object' ? (
                  <pre style={{ margin: 0, fontSize: 12, whiteSpace: 'pre-wrap' }}>
                    {JSON.stringify(v, null, 2)}
                  </pre>
                ) : String(v ?? '')}
              </Descriptions.Item>
            ))}
          </Descriptions>
        </Card>
      )}

      {treeData.length > 0 ? (
        <Card title="卷章结构" size="small">
          <Tree
            defaultExpandedKeys={treeData.slice(0, 2).map((t) => t.key)}
            treeData={treeData}
            showLine
          />
        </Card>
      ) : (
        <Typography.Text type="secondary">暂无卷章数据</Typography.Text>
      )}
    </div>
  );
}
