import { useState, useMemo } from 'react';
import { Modal, Card, Checkbox, Space, Tag, Typography, Row, Col, Button } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, MinusCircleOutlined } from '@ant-design/icons';
import type { BatchFieldResult } from '@/api/types';

interface SmartEnhanceModalProps {
  open: boolean;
  onClose: () => void;
  results: BatchFieldResult[];
  fieldLabels: Record<string, string>;
  processingTime: number;
  onApply: (acceptedFields: Record<string, string>) => void;
}

export default function SmartEnhanceModal({
  open,
  onClose,
  results,
  fieldLabels,
  processingTime,
  onApply,
}: SmartEnhanceModalProps) {
  const [acceptedFields, setAcceptedFields] = useState<Set<string>>(new Set());

  // 成功生成的字段列表
  const successResults = useMemo(
    () => results.filter((r) => r.status === 'success'),
    [results],
  );

  // 统计信息
  const stats = useMemo(() => {
    const success = results.filter((r) => r.status === 'success').length;
    const skipped = results.filter((r) => r.status === 'skipped').length;
    const failed = results.filter((r) => r.status === 'failed').length;
    return { success, skipped, failed };
  }, [results]);

  // 弹窗打开动画完成后，默认勾选所有成功字段（使用事件回调替代 useEffect）
  const handleAfterOpenChange = (isOpen: boolean) => {
    if (isOpen) {
      setAcceptedFields(new Set(successResults.map((r) => r.field_name)));
    }
  };

  const toggleField = (fieldName: string) => {
    setAcceptedFields((prev) => {
      const next = new Set(prev);
      if (next.has(fieldName)) {
        next.delete(fieldName);
      } else {
        next.add(fieldName);
      }
      return next;
    });
  };

  const handleApply = () => {
    const fields: Record<string, string> = {};
    for (const result of successResults) {
      if (acceptedFields.has(result.field_name)) {
        fields[result.field_name] = result.suggestion;
      }
    }
    onApply(fields);
  };

  const acceptedCount = acceptedFields.size;

  return (
    <Modal
      title="智能完善结果"
      open={open}
      onCancel={onClose}
      afterOpenChange={handleAfterOpenChange}
      width={720}
      footer={[
        <Button key="cancel" onClick={onClose}>
          取消
        </Button>,
        <Button
          key="apply"
          type="primary"
          disabled={acceptedCount === 0}
          onClick={handleApply}
        >
          应用选中字段 ({acceptedCount})
        </Button>,
      ]}
    >
      {/* 统计栏 */}
      <Space style={{ marginBottom: 16 }}>
        {stats.success > 0 && (
          <Tag icon={<CheckCircleOutlined />} color="success">
            成功 {stats.success}
          </Tag>
        )}
        {stats.skipped > 0 && (
          <Tag icon={<MinusCircleOutlined />} color="default">
            跳过 {stats.skipped}
          </Tag>
        )}
        {stats.failed > 0 && (
          <Tag icon={<CloseCircleOutlined />} color="error">
            失败 {stats.failed}
          </Tag>
        )}
        <Typography.Text type="secondary">
          耗时 {processingTime} 秒
        </Typography.Text>
      </Space>

      {/* 字段对比列表 */}
      <div style={{ maxHeight: 480, overflowY: 'auto' }}>
        {results.map((result) => {
          const label = fieldLabels[result.field_name] || result.field_name;

          if (result.status === 'skipped') {
            return (
              <Card
                key={result.field_name}
                size="small"
                style={{ marginBottom: 8, opacity: 0.6 }}
              >
                <Space>
                  <MinusCircleOutlined style={{ color: '#999' }} />
                  <Typography.Text type="secondary" delete>
                    {label}
                  </Typography.Text>
                  <Tag>已跳过 - 保留用户编辑</Tag>
                </Space>
              </Card>
            );
          }

          if (result.status === 'failed') {
            return (
              <Card
                key={result.field_name}
                size="small"
                style={{ marginBottom: 8, borderColor: '#ff4d4f' }}
              >
                <Space>
                  <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                  <Typography.Text type="danger">{label}</Typography.Text>
                  <Typography.Text type="secondary">
                    {result.error_message || '生成失败'}
                  </Typography.Text>
                </Space>
              </Card>
            );
          }

          // 成功生成的字段 - 显示对比
          return (
            <Card
              key={result.field_name}
              size="small"
              style={{ marginBottom: 8 }}
            >
              <Checkbox
                checked={acceptedFields.has(result.field_name)}
                onChange={() => toggleField(result.field_name)}
                style={{ marginBottom: 8 }}
              >
                <Typography.Text strong>{label}</Typography.Text>
              </Checkbox>
              <Row gutter={12}>
                <Col span={12}>
                  <div style={{ padding: 8, background: '#fafafa', borderRadius: 4, minHeight: 60 }}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      原始值
                    </Typography.Text>
                    <div style={{ marginTop: 4 }}>
                      {result.original_value ? (
                        <Typography.Paragraph
                          style={{ margin: 0, fontSize: 13 }}
                          ellipsis={{ rows: 4, expandable: true }}
                        >
                          {result.original_value}
                        </Typography.Paragraph>
                      ) : (
                        <Typography.Text type="secondary" italic>
                          (空)
                        </Typography.Text>
                      )}
                    </div>
                  </div>
                </Col>
                <Col span={12}>
                  <div style={{ padding: 8, background: '#f0f9ff', borderRadius: 4, minHeight: 60 }}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      AI 建议
                    </Typography.Text>
                    <div style={{ marginTop: 4 }}>
                      <Typography.Paragraph
                        style={{ margin: 0, fontSize: 13 }}
                        ellipsis={{ rows: 4, expandable: true }}
                      >
                        {result.suggestion}
                      </Typography.Paragraph>
                    </div>
                  </div>
                </Col>
              </Row>
            </Card>
          );
        })}
      </div>
    </Modal>
  );
}
