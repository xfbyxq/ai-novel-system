import { useState } from 'react';
import {
  Modal,
  Tabs,
  Card,
  Descriptions,
  List,
  Typography,
  Button,
  Space,
  Tag,
  Progress,
  Row,
  Col,
  Divider,
} from 'antd';
import {
  DiffOutlined,
  CheckCircleOutlined,
  ArrowUpOutlined,
  StarOutlined,
} from '@ant-design/icons';
import type { EnhancementPreviewResponse } from '@/api/types';

interface Props {
  visible: boolean;
  onClose: () => void;
  originalOutline: Record<string, unknown>;
  enhancedOutline: Record<string, unknown>;
  qualityComparison: EnhancementPreviewResponse['quality_comparison'];
  improvementsMade: string[];
  processingTime: number;
  costEstimate: number;
  onApply: (enhancedOutline: Record<string, unknown>) => void;
}

export default function EnhancementComparisonModal({
  visible,
  onClose,
  originalOutline,
  enhancedOutline,
  qualityComparison,
  improvementsMade,
  processingTime,
  costEstimate,
  onApply,
}: Props) {
  const [activeTab, setActiveTab] = useState('comparison');

  const handleApply = () => {
    onApply(enhancedOutline);
    onClose();
  };

  const formatFieldLabel = (fieldName: string) => {
    const fieldLabels: Record<string, string> = {
      core_conflict: '核心冲突',
      protagonist_goal: '主角目标',
      antagonist: '反派/阻碍',
      progression_path: '升级路径',
      emotional_arc: '情感弧光',
      key_revelations: '关键揭示',
      character_growth: '角色成长',
      resolution: '结局描述',
    };
    return fieldLabels[fieldName] || fieldName;
  };

  const renderOutlineDiff = (fieldName: string) => {
    const originalValue = (originalOutline[fieldName] as string) || '';
    const enhancedValue = (enhancedOutline[fieldName] as string) || '';
    
    return (
      <div key={fieldName}>
        <Typography.Title level={5} style={{ marginBottom: 8 }}>
          {formatFieldLabel(fieldName)}
        </Typography.Title>
        <Row gutter={16}>
          <Col span={12}>
            <Card 
              size="small" 
              title="原始内容" 
              type="inner"
              style={{ height: '100%' }}
            >
              <div style={{ 
                whiteSpace: 'pre-wrap', 
                minHeight: 60,
                color: originalValue ? 'inherit' : '#ccc'
              }}>
                {originalValue || '（空）'}
              </div>
            </Card>
          </Col>
          <Col span={12}>
            <Card 
              size="small" 
              title="优化后内容" 
              type="inner"
              style={{ 
                height: '100%',
                borderColor: enhancedValue !== originalValue ? '#52c41a' : undefined
              }}
            >
              <div style={{ 
                whiteSpace: 'pre-wrap', 
                minHeight: 60,
                color: enhancedValue ? 'inherit' : '#ccc'
              }}>
                {enhancedValue || '（空）'}
              </div>
              {enhancedValue !== originalValue && enhancedValue && (
                <Tag color="success" icon={<StarOutlined />} style={{ marginTop: 8 }}>
                  已优化
                </Tag>
              )}
            </Card>
          </Col>
        </Row>
        <Divider style={{ margin: '16px 0' }} />
      </div>
    );
  };

  const allFields = [
    'core_conflict',
    'protagonist_goal', 
    'antagonist',
    'progression_path',
    'emotional_arc',
    'key_revelations',
    'character_growth',
    'resolution'
  ];

  return (
    <Modal
      title={
        <Space>
          <DiffOutlined />
          智能完善结果对比
        </Space>
      }
      open={visible}
      onCancel={onClose}
      width={1000}
      footer={[
        <Button key="cancel" onClick={onClose}>
          取消
        </Button>,
        <Button 
          key="apply" 
          type="primary" 
          onClick={handleApply}
          icon={<CheckCircleOutlined />}
        >
          应用优化结果
        </Button>
      ]}
    >
      <Tabs 
        activeKey={activeTab} 
        onChange={setActiveTab}
        items={[
          {
            key: 'comparison',
            label: '内容对比',
            children: (
              <div style={{ maxHeight: 400, overflow: 'auto' }}>
                {allFields.map(field => {
                  const hasChanges = (originalOutline[field] || '') !== (enhancedOutline[field] || '');
                  if (hasChanges || enhancedOutline[field]) {
                    return renderOutlineDiff(field);
                  }
                  return null;
                })}
                {!allFields.some(field => 
                  (originalOutline[field] || '') !== (enhancedOutline[field] || '') || enhancedOutline[field]
                ) && (
                  <div style={{ textAlign: 'center', padding: 40 }}>
                    <Typography.Text type="secondary">
                      未检测到明显的内容变更
                    </Typography.Text>
                  </div>
                )}
              </div>
            )
          },
          {
            key: 'quality',
            label: '质量提升',
            children: (
              <div>
                <Card title="整体评分变化" size="small" style={{ marginBottom: 16 }}>
                  <Row gutter={16}>
                    <Col span={8}>
                      <div style={{ textAlign: 'center' }}>
                        <Typography.Title level={4} style={{ margin: 0, color: '#1890ff' }}>
                          {qualityComparison.original_score.toFixed(1)}
                        </Typography.Title>
                        <Typography.Text type="secondary">原始评分</Typography.Text>
                      </div>
                    </Col>
                    <Col span={8}>
                      <div style={{ textAlign: 'center' }}>
                        <ArrowUpOutlined style={{ 
                          fontSize: 24, 
                          color: qualityComparison.improvement > 0 ? '#52c41a' : '#faad14',
                          transform: qualityComparison.improvement > 0 ? 'none' : 'rotate(180deg)'
                        }} />
                        <div style={{ margin: '8px 0' }}>
                          <Typography.Text strong style={{ 
                            color: qualityComparison.improvement > 0 ? '#52c41a' : '#faad14'
                          }}>
                            {qualityComparison.improvement > 0 ? '+' : ''}{qualityComparison.improvement.toFixed(1)}
                          </Typography.Text>
                        </div>
                      </div>
                    </Col>
                    <Col span={8}>
                      <div style={{ textAlign: 'center' }}>
                        <Typography.Title level={4} style={{ margin: 0, color: '#52c41a' }}>
                          {qualityComparison.enhanced_score.toFixed(1)}
                        </Typography.Title>
                        <Typography.Text type="secondary">优化后评分</Typography.Text>
                      </div>
                    </Col>
                  </Row>
                  
                  <Progress
                    percent={Math.round(((qualityComparison.enhanced_score - qualityComparison.original_score) / 10) * 100 + 50)}
                    format={() => `${qualityComparison.improvement > 0 ? '+' : ''}${qualityComparison.improvement.toFixed(1)}分`}
                    strokeColor={qualityComparison.improvement > 0 ? '#52c41a' : '#faad14'}
                    style={{ marginTop: 16 }}
                  />
                </Card>

                <Card title="各维度提升" size="small">
                  <List
                    dataSource={Object.entries(qualityComparison.dimension_improvements)}
                    renderItem={([dimension, improvement]) => (
                      <List.Item>
                        <Descriptions size="small" column={3}>
                          <Descriptions.Item label="维度">
                            {dimension.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')}
                          </Descriptions.Item>
                          <Descriptions.Item label="提升值">
                            <Space>
                              <Typography.Text 
                                strong 
                                style={{ color: improvement > 0 ? '#52c41a' : '#faad14' }}
                              >
                                {improvement > 0 ? '+' : ''}{improvement.toFixed(1)}
                              </Typography.Text>
                              {improvement > 0 && <ArrowUpOutlined style={{ color: '#52c41a' }} />}
                            </Space>
                          </Descriptions.Item>
                          <Descriptions.Item label="状态">
                            <Tag color={improvement > 0 ? 'success' : improvement < 0 ? 'error' : 'default'}>
                              {improvement > 0 ? '提升' : improvement < 0 ? '下降' : '持平'}
                            </Tag>
                          </Descriptions.Item>
                        </Descriptions>
                      </List.Item>
                    )}
                  />
                </Card>
              </div>
            )
          },
          {
            key: 'summary',
            label: '优化摘要',
            children: (
              <div>
                <Card title="处理信息" size="small" style={{ marginBottom: 16 }}>
                  <Descriptions column={2} size="small">
                    <Descriptions.Item label="处理耗时">
                      {processingTime.toFixed(1)} 秒
                    </Descriptions.Item>
                    <Descriptions.Item label="预估成本">
                      ¥{costEstimate.toFixed(2)}
                    </Descriptions.Item>
                  </Descriptions>
                </Card>

                <Card title="主要改进" size="small">
                  {improvementsMade.length > 0 ? (
                    <List
                      dataSource={improvementsMade}
                      renderItem={(improvement, index) => (
                        <List.Item>
                          <Space>
                            <Tag color="processing">{index + 1}</Tag>
                            <Typography.Text>{improvement}</Typography.Text>
                          </Space>
                        </List.Item>
                      )}
                    />
                  ) : (
                    <div style={{ textAlign: 'center', padding: 20 }}>
                      <Typography.Text type="secondary">
                        未生成具体的改进列表
                      </Typography.Text>
                    </div>
                  )}
                </Card>
              </div>
            )
          }
        ]}
      />
    </Modal>
  );
}