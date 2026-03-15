import { useEffect, useState, useCallback } from 'react';
import { Spin, Empty, Tree, Card, Typography, Descriptions, Button, Space, Modal, List, Tag } from 'antd';
import { RocketOutlined, EditOutlined, HistoryOutlined } from '@ant-design/icons';
import type { PlotOutline } from '@/api/types';
import { getPlotOutline, getOutlineVersions } from '@/api/outlines';
import { formatDate } from '@/utils/format';

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

interface OutlineVersion {
  version_id: string;
  version_number: number;
  created_at: string;
  created_by?: string;
  change_summary?: string;
}

export default function PlotOutlineTab({ novelId }: Props) {
  const [outline, setOutline] = useState<PlotOutline | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [versionsVisible, setVersionsVisible] = useState(false);
  const [versions, setVersions] = useState<OutlineVersion[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);

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

  const handleOpenVersions = useCallback(async () => {
    setVersionsVisible(true);
    setVersionsLoading(true);
    try {
      const data = await getOutlineVersions(novelId);
      setVersions(data);
    } catch (err) {
      console.error('Failed to fetch versions:', err);
    } finally {
      setVersionsLoading(false);
    }
  }, [novelId]);

  const handleCloseVersions = useCallback(() => {
    setVersionsVisible(false);
    setVersions([]);
  }, []);

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
          <Descriptions.Item label="更新时间">{formatDate(outline.updated_at)}</Descriptions.Item>
        </Descriptions>
        <Space style={{ marginTop: 16 }}>
          <Button 
            icon={<EditOutlined />} 
            onClick={() => {
              const refineTab = document.querySelector('[data-node-key="outline-refine"]') as HTMLElement;
              refineTab?.click();
            }}
          >
            进入大纲梳理
          </Button>
          <Button 
            icon={<HistoryOutlined />} 
            onClick={handleOpenVersions}
          >
            查看版本历史
          </Button>
        </Space>
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

      <Modal
        title="大纲版本历史"
        open={versionsVisible}
        onCancel={handleCloseVersions}
        footer={null}
        width={800}
      >
        {versionsLoading ? (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Spin />
          </div>
        ) : versions.length > 0 ? (
          <List
            dataSource={versions}
            renderItem={(item) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <Space>
                      <Tag color="blue">版本 {item.version_number}</Tag>
                      <Typography.Text strong>{item.change_summary || '无变更说明'}</Typography.Text>
                    </Space>
                  }
                  description={
                    <Space orientation="vertical" size="small" style={{ width: '100%' }}>
                      <Typography.Text type="secondary">
                        创建时间：{formatDate(item.created_at)}
                      </Typography.Text>
                      {item.created_by && (
                        <Typography.Text type="secondary">
                          创建者：{item.created_by}
                        </Typography.Text>
                      )}
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        ) : (
          <Empty description="暂无版本历史" />
        )}
      </Modal>
    </div>
  );
}
