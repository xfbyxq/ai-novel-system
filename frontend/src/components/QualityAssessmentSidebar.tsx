import { useState, useEffect } from 'react';
import {
  Card,
  Progress,
  List,
  Tag,
  Spin,
  Empty,
  Typography,
  Space,
  Button,
  Tooltip,
  Badge,
} from 'antd';
import {
  ReloadOutlined,
  BulbOutlined,
  CheckCircleOutlined,
  WarningOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
import type { OutlineQualityReport } from '@/api/types';

interface Props {
  novelId: string;
  loading?: boolean;
  onRefresh?: () => void;
}

const DIMENSION_LABELS: Record<string, string> = {
  structure_completeness: '结构完整性',
  setting_consistency: '世界观一致性',
  character_coherence: '角色连贯性',
  tension_management: '张力控制',
  logical_flow: '逻辑连贯性',
  innovation_factor: '创新性',
};

const DIMENSION_COLORS: Record<string, string> = {
  structure_completeness: '#1890ff',
  setting_consistency: '#52c41a',
  character_coherence: '#722ed1',
  tension_management: '#fa8c16',
  logical_flow: '#13c2c2',
  innovation_factor: '#eb2f96',
};

export default function QualityAssessmentSidebar({
  novelId,
  loading = false,
  onRefresh,
}: Props) {
  const [qualityReport, setQualityReport] = useState<OutlineQualityReport | null>(null);
  const [localLoading, setLocalLoading] = useState(false);

  const fetchQualityReport = async () => {
    setLocalLoading(true);
    try {
      const response = await fetch(`/api/novels/${novelId}/outline/quality-report`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setQualityReport(data);
    } catch (error) {
      console.error('获取质量报告失败:', error);
      // 这里可以添加错误处理，比如显示错误消息
    } finally {
      setLocalLoading(false);
    }
  };

  useEffect(() => {
    if (novelId) {
      void fetchQualityReport();
    }
  }, [novelId]);

  const handleRefresh = () => {
    void fetchQualityReport();
    onRefresh?.();
  };

  const getProgressStatus = (score: number) => {
    if (score >= 8) return 'success';
    if (score >= 6) return 'normal';
    return 'exception';
  };

  const getOverallScoreColor = (score: number) => {
    if (score >= 8) return '#52c41a';
    if (score >= 6) return '#faad14';
    return '#ff4d4f';
  };

  const isLoading = loading || localLoading;

  if (isLoading) {
    return (
      <Card size="small" style={{ width: 320 }}>
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin tip="正在评估大纲质量..." />
        </div>
      </Card>
    );
  }

  if (!qualityReport) {
    return (
      <Card 
        size="small" 
        style={{ width: 320 }}
        title="质量评估"
        extra={
          <Button 
            type="text" 
            icon={<ReloadOutlined />} 
            onClick={handleRefresh}
            size="small"
          />
        }
      >
        <Empty 
          description="暂无质量评估数据" 
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <Button type="primary" onClick={handleRefresh}>
            开始评估
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card
      size="small"
      style={{ width: 320 }}
      title={
        <Space>
          <span>质量评估</span>
          <Badge 
            count={Math.round(qualityReport.overall_score * 10) / 10} 
            style={{ backgroundColor: getOverallScoreColor(qualityReport.overall_score) }}
          />
        </Space>
      }
      extra={
        <Tooltip title="刷新评估">
          <Button 
            type="text" 
            icon={<ReloadOutlined />} 
            onClick={handleRefresh}
            size="small"
          />
        </Tooltip>
      }
    >
      {/* 综合评分 */}
      <div style={{ textAlign: 'center', marginBottom: 24 }}>
        <Progress
          type="circle"
          percent={Math.round(qualityReport.overall_score * 10)}
          format={(percent) => `${(percent ?? 0) / 10}分`}
          strokeColor={getOverallScoreColor(qualityReport.overall_score)}
          width={120}
        />
        <div style={{ marginTop: 8 }}>
          <Typography.Text strong>
            综合评分
          </Typography.Text>
        </div>
      </div>

      {/* 各维度评分 */}
      <div style={{ marginBottom: 24 }}>
        <Typography.Title level={5} style={{ marginBottom: 12 }}>
          <Space>
            <InfoCircleOutlined />
            维度分析
          </Space>
        </Typography.Title>
        <List
          size="small"
          dataSource={Object.entries(qualityReport.dimension_scores)}
          renderItem={([key, score]) => (
            <List.Item style={{ padding: '4px 0' }}>
              <div style={{ width: '100%' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <Typography.Text strong style={{ fontSize: 12 }}>
                    {DIMENSION_LABELS[key] || key}
                  </Typography.Text>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {score.toFixed(1)}/10
                  </Typography.Text>
                </div>
                <Progress
                  percent={Math.round(score * 10)}
                  size="small"
                  status={getProgressStatus(score)}
                  strokeColor={DIMENSION_COLORS[key] || '#1890ff'}
                  showInfo={false}
                />
              </div>
            </List.Item>
          )}
        />
      </div>

      {/* 优势分析 */}
      {qualityReport.strengths.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <Typography.Title level={5} style={{ marginBottom: 12 }}>
            <Space>
              <CheckCircleOutlined style={{ color: '#52c41a' }} />
              优势亮点
            </Space>
          </Typography.Title>
          <Space wrap>
            {qualityReport.strengths.map((strength, index) => (
              <Tag key={index} color="success" icon={<CheckCircleOutlined />}>
                {strength}
              </Tag>
            ))}
          </Space>
        </div>
      )}

      {/* 改进建议 */}
      {qualityReport.improvement_suggestions.length > 0 && (
        <div>
          <Typography.Title level={5} style={{ marginBottom: 12 }}>
            <Space>
              <BulbOutlined style={{ color: '#faad14' }} />
              改进建议
            </Space>
          </Typography.Title>
          <List
            size="small"
            dataSource={qualityReport.improvement_suggestions}
            renderItem={(suggestion) => (
              <List.Item style={{ padding: '8px 0' }}>
                <Space orientation="vertical" size="small" style={{ width: '100%' }}>
                  <div>
                    <Tag 
                      color={suggestion.priority === 'high' ? 'error' : suggestion.priority === 'medium' ? 'warning' : 'default'}
                      icon={suggestion.priority === 'high' ? <WarningOutlined /> : <BulbOutlined />}
                    >
                      {suggestion.priority === 'high' ? '高优先级' : suggestion.priority === 'medium' ? '中优先级' : '低优先级'}
                    </Tag>
                    <Typography.Text strong style={{ marginLeft: 8 }}>
                      {suggestion.description}
                    </Typography.Text>
                  </div>
                  {suggestion.details && suggestion.details.length > 0 && (
                    <ul style={{ margin: 0, paddingLeft: 16 }}>
                      {suggestion.details.map((detail, detailIndex) => (
                        <li key={detailIndex} style={{ fontSize: 12, color: '#666' }}>
                          {detail}
                        </li>
                      ))}
                    </ul>
                  )}
                </Space>
              </List.Item>
            )}
          />
        </div>
      )}

      {/* 无建议时的鼓励信息 */}
      {qualityReport.improvement_suggestions.length === 0 && qualityReport.strengths.length > 0 && (
        <div style={{ textAlign: 'center', padding: '16px 0' }}>
          <Typography.Text type="success">
            <CheckCircleOutlined /> 恭喜！您的大纲质量已经很不错了！
          </Typography.Text>
        </div>
      )}
    </Card>
  );
}