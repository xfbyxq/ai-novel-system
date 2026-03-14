import { useState, useCallback, useEffect } from 'react';
import {
  Card,
  Form,
  Input,
  Button,
  Progress,
  Space,
  Typography,
  Row,
  Col,
  Tooltip,
  message,
  Divider,
} from 'antd';
import {
  RobotOutlined,
  SaveOutlined,
  CheckCircleOutlined,
  EditOutlined,
} from '@ant-design/icons';
import type { PlotOutline } from '@/api/types';
import { getPlotOutline, updatePlotOutline } from '@/api/outlines';

interface MainPlot {
  core_conflict?: string;
  protagonist_goal?: string;
  antagonist?: string;
  progression_path?: string;
  emotional_arc?: string;
  key_revelations?: string;
  character_growth?: string;
  resolution?: string;
  [key: string]: unknown;
}

interface Props {
  novelId: string;
  onOutlineUpdate?: () => void;
}

const PLOT_FIELDS = [
  { name: 'core_conflict', label: '核心冲突', placeholder: '描述故事的主要矛盾和冲突' },
  { name: 'protagonist_goal', label: '主角目标', placeholder: '主角想要达成的目标' },
  { name: 'antagonist', label: '反派/阻碍', placeholder: '反派角色或主要阻碍' },
  { name: 'progression_path', label: '升级路径', placeholder: '力量体系或成长路径' },
  { name: 'emotional_arc', label: '情感弧光', placeholder: '主角的情感变化历程' },
  { name: 'key_revelations', label: '关键揭示', placeholder: '故事中的重要揭示和转折' },
  { name: 'character_growth', label: '角色成长', placeholder: '角色的成长和变化' },
  { name: 'resolution', label: '结局描述', placeholder: '故事的结局' },
];

export default function OutlineRefinementTab({ novelId, onOutlineUpdate }: Props) {
  const [form] = Form.useForm();
  const [outline, setOutline] = useState<PlotOutline | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [completeness, setCompleteness] = useState(0);

  const fetchOutline = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getPlotOutline(novelId);
      setOutline(data);
      
      const mainPlot = (data.main_plot || {}) as MainPlot;
      const formValues: Record<string, string> = {};
      
      PLOT_FIELDS.forEach((field) => {
        const value = mainPlot[field.name];
        formValues[field.name] = typeof value === 'string' ? value : (value ? JSON.stringify(value) : '');
      });
      
      form.setFieldsValue(formValues);
      calculateCompleteness(mainPlot);
    } catch (error) {
      console.error('Failed to fetch outline:', error);
      message.error('加载大纲失败');
    } finally {
      setLoading(false);
    }
  }, [novelId, form]);

  useEffect(() => {
    void fetchOutline();
  }, [fetchOutline]);

  const calculateCompleteness = (mainPlot: MainPlot) => {
    const filledFields = PLOT_FIELDS.filter((field) => {
      const value = mainPlot[field.name];
      return value && String(value).trim().length > 0;
    }).length;
    const percentage = Math.round((filledFields / PLOT_FIELDS.length) * 100);
    setCompleteness(percentage);
  };

  const handleAIAssist = useCallback(async (fieldName: string) => {
    const currentValues = form.getFieldsValue();
    const context = {
      fieldName,
      currentValue: currentValues[fieldName],
      novelInfo: {
        title: outline?.novel_id,
        genre: 'unknown',
      },
      otherFields: currentValues,
    };

    message.loading('AI 正在生成建议...', 0);
    
    try {
      const response = await fetch(`/api/novels/${novelId}/outline/ai-assist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(context),
      });

      if (!response.ok) throw new Error('AI 服务响应失败');
      
      const data = await response.json();
      const suggestion = data.suggestion || data.content || data.text;
      
      if (suggestion) {
        form.setFieldValue(fieldName, suggestion);
        message.success('AI 建议已填充');
        
        const updatedValues = form.getFieldsValue();
        calculateCompleteness(updatedValues as MainPlot);
      } else {
        message.warning('AI 未返回有效建议');
      }
    } catch (error) {
      console.error('AI assist error:', error);
      message.error('AI 辅助失败，请稍后重试');
    }
  }, [novelId, form, outline]);

  const handleSaveDraft = useCallback(async () => {
    setSaving(true);
    try {
      const values = await form.validateFields();
      const mainPlot: MainPlot = {};
      
      PLOT_FIELDS.forEach((field) => {
        if (values[field.name]) {
          mainPlot[field.name] = values[field.name];
        }
      });

      await updatePlotOutline(novelId, { main_plot: mainPlot as Record<string, unknown> });
      message.success('草稿已保存');
      onOutlineUpdate?.();
    } catch (error) {
      console.error('Save draft error:', error);
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  }, [novelId, form, onOutlineUpdate]);

  const handleConfirmOutline = useCallback(async () => {
    const values = await form.validateFields();
    const mainPlot: MainPlot = {};
    
    PLOT_FIELDS.forEach((field) => {
      if (values[field.name]) {
        mainPlot[field.name] = values[field.name];
      }
    });

    const filledCount = Object.keys(mainPlot).length;
    if (filledCount < PLOT_FIELDS.length - 2) {
      message.warning('请至少完成大部分要素后再确认大纲');
      return;
    }

    try {
      await updatePlotOutline(novelId, { 
        main_plot: mainPlot as Record<string, unknown>,
      });
      message.success('大纲已确认');
      onOutlineUpdate?.();
    } catch (error) {
      console.error('Confirm outline error:', error);
      message.error('确认失败');
    }
  }, [novelId, form, onOutlineUpdate]);

  const handleFormChange = useCallback(() => {
    const values = form.getFieldsValue();
    calculateCompleteness(values as MainPlot);
  }, [form]);

  const getProgressColor = (percent: number) => {
    if (percent < 30) return '#ff4d4f';
    if (percent < 60) return '#faad14';
    if (percent < 80) return '#1890ff';
    return '#52c41a';
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Typography.Text>加载大纲中...</Typography.Text>
      </div>
    );
  }

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Row align="middle" gutter={16}>
          <Col flex="auto">
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Typography.Title level={5} style={{ margin: 0 }}>
                大纲完整度
              </Typography.Title>
              <Progress
                percent={completeness}
                strokeColor={getProgressColor(completeness)}
                format={(percent) => `${percent}% (${PLOT_FIELDS.filter((f) => form.getFieldValue(f.name)).length}/${PLOT_FIELDS.length})`}
              />
            </Space>
          </Col>
          <Col>
            <Space>
              <Button
                icon={<SaveOutlined />}
                onClick={handleSaveDraft}
                loading={saving}
              >
                保存草稿
              </Button>
              <Button
                type="primary"
                icon={<CheckCircleOutlined />}
                onClick={handleConfirmOutline}
                loading={saving}
              >
                确认大纲
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Form form={form} layout="vertical" onValuesChange={handleFormChange}>
        <Row gutter={[16, 16]}>
          {PLOT_FIELDS.map((field) => {
            const currentValue = form.getFieldValue(field.name);
            const hasValue = currentValue && String(currentValue).trim().length > 0;

            return (
              <Col span={24} key={field.name}>
                <Card
                  size="small"
                  title={
                    <Space>
                      <EditOutlined />
                      {field.label}
                    </Space>
                  }
                  extra={
                    <Tooltip title="AI 辅助生成">
                      <Button
                        type="text"
                        icon={<RobotOutlined />}
                        onClick={() => handleAIAssist(field.name)}
                        disabled={loading}
                      />
                    </Tooltip>
                  }
                >
                  <Form.Item
                    name={field.name}
                    rules={[{ required: false }]}
                  >
                    <Input.TextArea
                      rows={3}
                      placeholder={field.placeholder}
                      showCount
                      maxLength={2000}
                      style={{ resize: 'vertical' }}
                    />
                  </Form.Item>
                  {hasValue && (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      已完成
                    </Typography.Text>
                  )}
                </Card>
              </Col>
            );
          })}
        </Row>
      </Form>

      <Divider />

      <Card
        size="small"
        title="操作提示"
        type="inner"
      >
        <Typography.Paragraph style={{ margin: 0 }}>
          <Typography.Text type="secondary">
            💡 建议按顺序填写各要素，AI 辅助会根据已有内容提供更精准的建议。
            完成度达到 80% 以上即可确认大纲，进入章节拆分阶段。
          </Typography.Text>
        </Typography.Paragraph>
      </Card>
    </div>
  );
}
