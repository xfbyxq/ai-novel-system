// 临时修复章节拆分功能的调试版本
import { useState, useCallback, useEffect } from 'react';
import {
  Card,
  Typography,
  Button,
  Space,
  Row,
  Col,
  message,
  Spin,
} from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import type { PlotOutline } from '@/api/types';
import { getPlotOutline } from '@/api/outlines';

interface Props {
  novelId: string;
}

export default function ChapterDecompositionTab({ novelId }: Props) {
  const [loading, setLoading] = useState(true);
  const [outline, setOutline] = useState<PlotOutline | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchOutline = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      console.log('🚀 开始获取大纲数据，novelId:', novelId);
      const data = await getPlotOutline(novelId);
      console.log('✅ 大纲数据获取成功:', data);
      setOutline(data);
      message.success('大纲加载成功');
    } catch (error: any) {
      console.error('❌ 获取大纲失败:', error);
      const errorMsg = error.response?.data?.detail || error.message || '未知错误';
      setError(errorMsg);
      message.error(`加载大纲失败: ${errorMsg}`);
    } finally {
      setLoading(false);
    }
  }, [novelId]);

  useEffect(() => {
    void fetchOutline();
  }, [fetchOutline]);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>正在加载大纲数据...</div>
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '50px 0' }}>
          <Typography.Title level={4} type="danger">
            ⚠️ 加载大纲失败
          </Typography.Title>
          <Typography.Paragraph type="secondary">
            错误信息: {error}
          </Typography.Paragraph>
          <Button 
            type="primary" 
            icon={<ReloadOutlined />}
            onClick={() => void fetchOutline()}
          >
            重新加载
          </Button>
        </div>
      </Card>
    );
  }

  if (!outline) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '50px 0' }}>
          <Typography.Title level={4}>
            📝 暂无大纲数据
          </Typography.Title>
          <Typography.Paragraph>
            请先在"大纲"标签页创建小说大纲
          </Typography.Paragraph>
        </div>
      </Card>
    );
  }

  return (
    <div>
      <Card 
        title="章节拆分" 
        extra={
          <Button 
            icon={<ReloadOutlined />} 
            onClick={() => void fetchOutline()}
          >
            刷新大纲
          </Button>
        }
      >
        <Row gutter={[16, 16]}>
          <Col span={24}>
            <Typography.Title level={5}>已加载的大纲信息</Typography.Title>
            <Space direction="vertical">
              <Typography.Text><strong>结构类型:</strong> {outline.structure_type}</Typography.Text>
              <Typography.Text><strong>卷数:</strong> {(outline.volumes || []).length} 卷</Typography.Text>
              <Typography.Text><strong>主线剧情:</strong> {outline.main_plot?.setup || '暂无'}</Typography.Text>
            </Space>
          </Col>
        </Row>
      </Card>
    </div>
  );
}