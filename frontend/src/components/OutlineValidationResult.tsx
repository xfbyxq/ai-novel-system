import { Card, Typography, Space, Progress, Tag, Button, Divider, Alert, Collapse } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  WarningOutlined,
  EditOutlined,
  RightOutlined,
} from '@ant-design/icons';

export interface ValidationIssue {
  field: string;
  issue: string;
  suggestion: string;
  severity: 'error' | 'warning' | 'info';
}

export interface ValidationResult {
  pass_rate: number;
  passed_checks: string[];
  failed_checks: string[];
  missing_elements: string[];
  issues: ValidationIssue[];
  suggestions: string[];
}

interface OutlineValidationResultProps {
  result: ValidationResult | null;
  onModify?: () => void;
  onSkip?: () => void;
  showActions?: boolean;
}

export default function OutlineValidationResult({
  result,
  onModify,
  onSkip,
  showActions = true,
}: OutlineValidationResultProps) {
  if (!result) {
    return (
      <Typography.Text type="secondary">
        暂无验证结果
      </Typography.Text>
    );
  }

  const isPassed = result.pass_rate >= 80;
  const hasCriticalIssues = result.issues.some((i) => i.severity === 'error');

  const getProgressColor = () => {
    if (result.pass_rate < 50) return '#ff4d4f';
    if (result.pass_rate < 80) return '#faad14';
    return '#52c41a';
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'error':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      case 'warning':
        return <WarningOutlined style={{ color: '#faad14' }} />;
      case 'info':
        return <RightOutlined style={{ color: '#1890ff' }} />;
      default:
        return <RightOutlined />;
    }
  };

  const getSeverityTag = (severity: string) => {
    switch (severity) {
      case 'error':
        return <Tag color="red">错误</Tag>;
      case 'warning':
        return <Tag color="orange">警告</Tag>;
      case 'info':
        return <Tag color="blue">建议</Tag>;
      default:
        return <Tag>未知</Tag>;
    }
  };

  return (
    <div>
      <Card
        type="inner"
        size="small"
        style={{ marginBottom: 16 }}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <RowSpace>
            <Typography.Title level={5} style={{ margin: 0 }}>
              验证通过率
            </Typography.Title>
            <Tag color={isPassed ? 'green' : 'red'}>
              {isPassed ? '通过' : '未通过'}
            </Tag>
          </RowSpace>

          <Progress
            percent={result.pass_rate}
            strokeColor={getProgressColor()}
            format={(percent) => `${percent}% (${result.passed_checks.length}/${result.passed_checks.length + result.failed_checks.length})`}
          />

          {hasCriticalIssues && (
            <Alert
              message="存在严重问题"
              description="请先解决所有错误级别的问题后再确认大纲"
              type="error"
              showIcon
            />
          )}

          {!hasCriticalIssues && !isPassed && (
            <Alert
              message="建议优化"
              description="大纲基本合格，但仍有改进空间"
              type="warning"
              showIcon
            />
          )}

          {isPassed && (
            <Alert
              message="验证通过"
              description="大纲质量良好，可以继续进行下一步"
              type="success"
              showIcon
            />
          )}
        </Space>
      </Card>

      <Collapse accordion>
        {result.passed_checks.length > 0 && (
          <Collapse.Panel
            header={
              <Space>
                <CheckCircleOutlined style={{ color: '#52c41a' }} />
                <Typography.Text strong>
                  通过的检查 ({result.passed_checks.length})
                </Typography.Text>
              </Space>
            }
            key="passed"
          >
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              {result.passed_checks.map((check, index) => (
                <Space key={index}>
                  <CheckCircleOutlined style={{ color: '#52c41a' }} />
                  <Typography.Text>{check}</Typography.Text>
                </Space>
              ))}
            </Space>
          </Collapse.Panel>
        )}

        {result.failed_checks.length > 0 && (
          <Collapse.Panel
            header={
              <Space>
                <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                <Typography.Text strong>
                  未通过的检查 ({result.failed_checks.length})
                </Typography.Text>
              </Space>
            }
            key="failed"
          >
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              {result.failed_checks.map((check, index) => (
                <Space key={index}>
                  <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                  <Typography.Text>{check}</Typography.Text>
                </Space>
              ))}
            </Space>
          </Collapse.Panel>
        )}

        {result.missing_elements.length > 0 && (
          <Collapse.Panel
            header={
              <Space>
                <WarningOutlined style={{ color: '#faad14' }} />
                <Typography.Text strong>
                  缺失的要素 ({result.missing_elements.length})
                </Typography.Text>
              </Space>
            }
            key="missing"
          >
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              {result.missing_elements.map((element, index) => (
                <Space key={index}>
                  <WarningOutlined style={{ color: '#faad14' }} />
                  <Typography.Text>{element}</Typography.Text>
                </Space>
              ))}
            </Space>
          </Collapse.Panel>
        )}

        {result.issues.length > 0 && (
          <Collapse.Panel
            header={
              <Space>
                <EditOutlined />
                <Typography.Text strong>
                  问题详情与建议 ({result.issues.length})
                </Typography.Text>
              </Space>
            }
            key="issues"
          >
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              {result.issues.map((issue, index) => (
                <Card key={index} size="small" type="inner">
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    <Space>
                      {getSeverityIcon(issue.severity)}
                      {getSeverityTag(issue.severity)}
                      <Typography.Text strong>{issue.field}</Typography.Text>
                    </Space>
                    <Alert
                      message={issue.issue}
                      description={issue.suggestion}
                      type={issue.severity === 'error' ? 'error' : issue.severity === 'warning' ? 'warning' : 'info'}
                      showIcon
                    />
                  </Space>
                </Card>
              ))}
            </Space>
          </Collapse.Panel>
        )}

        {result.suggestions.length > 0 && (
          <Collapse.Panel
            header={
              <Space>
                <RightOutlined />
                <Typography.Text strong>
                  优化建议 ({result.suggestions.length})
                </Typography.Text>
              </Space>
            }
            key="suggestions"
          >
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              {result.suggestions.map((suggestion, index) => (
                <Space key={index}>
                  <RightOutlined style={{ color: '#1890ff' }} />
                  <Typography.Text>{suggestion}</Typography.Text>
                </Space>
              ))}
            </Space>
          </Collapse.Panel>
        )}
      </Collapse>

      {showActions && (
        <>
          <Divider />
          <Space style={{ justifyContent: 'flex-end', width: '100%' }}>
            <Button onClick={onSkip}>
              跳过
            </Button>
            <Button
              type="primary"
              icon={<EditOutlined />}
              onClick={onModify}
              disabled={result.issues.length === 0}
            >
              立即修改
            </Button>
          </Space>
        </>
      )}
    </div>
  );
}

function RowSpace({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      {children}
    </div>
  );
}
