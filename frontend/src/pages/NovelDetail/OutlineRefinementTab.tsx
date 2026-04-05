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
  Alert,
  Collapse,
  Tag,
  List,
  Empty,
  Tabs,
} from 'antd';
import {
  RobotOutlined,
  SaveOutlined,
  CheckCircleOutlined,
  EditOutlined,
  ThunderboltOutlined,
  BookOutlined,
  ProfileOutlined,
} from '@ant-design/icons';
import type { PlotOutline } from '@/api/types';
import { getPlotOutline, updatePlotOutline, aiAssistOutline } from '@/api/outlines';
import { createGenerationTask } from '@/api/generation';
import { useGenerationStore } from '@/stores/useGenerationStore';
import { useNavigate } from 'react-router-dom';

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

// 卷结构展示组件
interface VolumeStructurePanelProps {
  outline: PlotOutline | null;
}

function VolumeStructurePanel({ outline }: VolumeStructurePanelProps) {
  if (!outline?.volumes || outline.volumes.length === 0) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          <div>
            <Typography.Text type="secondary">
              暂无卷章结构数据
            </Typography.Text>
            <br />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              点击「智能完善」按钮可自动生成详细的卷章结构
            </Typography.Text>
          </div>
        }
      />
    );
  }

  const volumes = outline.volumes;

  return (
    <div>
      <Typography.Paragraph style={{ marginBottom: 16 }}>
        <Typography.Text type="secondary">
          共 {volumes.length} 卷，使用「智能完善」可生成更详细的卷结构
        </Typography.Text>
      </Typography.Paragraph>

      <Collapse defaultActiveKey={volumes.length > 0 ? ['0'] : []}>
        {volumes.map((vol, index) => {
          const volumeNum = vol.number || index + 1;
          const chapters = vol.chapters || [];
          const chapterRange = chapters.length >= 2
            ? `第${chapters[0]}-${chapters[1]}章`
            : (chapters.length === 1 ? `第${chapters[0]}章` : '章节待定');

          return (
            <Collapse.Panel
              key={String(index)}
              header={
                <Space>
                  <Tag color="blue">第{volumeNum}卷</Tag>
                  <Typography.Text strong>{vol.title || '未命名'}</Typography.Text>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {chapterRange}
                  </Typography.Text>
                </Space>
              }
            >
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                {/* 卷概要 */}
                {vol.summary && (
                  <div>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>概要：</Typography.Text>
                    <br />
                    <Typography.Text>{vol.summary}</Typography.Text>
                  </div>
                )}

                {/* 核心冲突 */}
                {vol.core_conflict && (
                  <div>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>核心冲突：</Typography.Text>
                    <br />
                    <Typography.Text>{vol.core_conflict}</Typography.Text>
                  </div>
                )}

                {/* 主线事件 */}
                {vol.main_events && vol.main_events.length > 0 && (
                  <div>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>主线事件：</Typography.Text>
                    <List
                      size="small"
                      dataSource={vol.main_events}
                      renderItem={(evt: unknown, idx: number) => {
                        const event = evt as { chapter?: number; event?: string; impact?: string };
                        return (
                          <List.Item key={idx}>
                            <Typography.Text style={{ fontSize: 12 }}>
                              <Tag style={{ fontSize: 11, padding: '0 4px' }}>第{event.chapter || '?'}章</Tag>
                              {' '}{event.event || '未命名事件'}
                              {event.impact && <span>（影响：{event.impact}）</span>}
                            </Typography.Text>
                          </List.Item>
                        );
                      }}
                    />
                  </div>
                )}

                {/* 关键转折点 */}
                {vol.key_turning_points && vol.key_turning_points.length > 0 && (
                  <div>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>关键转折点：</Typography.Text>
                    <List
                      size="small"
                      dataSource={vol.key_turning_points}
                      renderItem={(tp: unknown, idx: number) => {
                        const point = tp as { chapter?: number; event?: string; significance?: string };
                        return (
                          <List.Item key={idx}>
                            <Typography.Text style={{ fontSize: 12 }}>
                              <Tag color="orange" style={{ fontSize: 11, padding: '0 4px' }}>第{point.chapter || '?'}章</Tag>
                              {' '}{point.event || '未命名'}
                            </Typography.Text>
                          </List.Item>
                        );
                      }}
                    />
                  </div>
                )}

                {/* 情感弧线 */}
                {vol.emotional_arc && (
                  <div>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>情感弧线：</Typography.Text>
                    <br />
                    <Typography.Text style={{ fontSize: 12 }}>{vol.emotional_arc}</Typography.Text>
                  </div>
                )}

                {/* 支线情节 */}
                {vol.side_plots && vol.side_plots.length > 0 && (
                  <div>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>支线情节：</Typography.Text>
                    <List
                      size="small"
                      dataSource={vol.side_plots}
                      renderItem={(sp: unknown, idx: number) => {
                        const plot = sp as { name?: string; description?: string };
                        return (
                          <List.Item key={idx}>
                            <Typography.Text style={{ fontSize: 12 }}>
                              <Tag color="green" style={{ fontSize: 11, padding: '0 4px' }}>{plot.name || '支线'}</Tag>
                              {' '}{plot.description || ''}
                            </Typography.Text>
                          </List.Item>
                        );
                      }}
                    />
                  </div>
                )}

                {/* 伏笔 */}
                {vol.foreshadowing && vol.foreshadowing.length > 0 && (
                  <div>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>伏笔设置：</Typography.Text>
                    <List
                      size="small"
                      dataSource={vol.foreshadowing}
                      renderItem={(fs: unknown, idx: number) => {
                        const item = fs as { description?: string; setup_chapter?: number; payoff_chapter?: number };
                        return (
                          <List.Item key={idx}>
                            <Typography.Text style={{ fontSize: 12 }}>
                              {item.description || ''}
                              <span style={{ color: '#999' }}>
                                （第{item.setup_chapter || '?'}章设置 → 第{item.payoff_chapter || '?'}章回收）
                              </span>
                            </Typography.Text>
                          </List.Item>
                        );
                      }}
                    />
                  </div>
                )}

                {/* 主题 */}
                {vol.themes && vol.themes.length > 0 && (
                  <div>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>主题：</Typography.Text>
                    <Space size="small" wrap>
                      {vol.themes.map((theme: string, idx: number) => (
                        <Tag key={idx} color="purple" style={{ fontSize: 11, padding: '0 4px' }}>{theme}</Tag>
                      ))}
                    </Space>
                  </div>
                )}
              </Space>
            </Collapse.Panel>
          );
        })}
      </Collapse>
    </div>
  );
}

export default function OutlineRefinementTab({ novelId, onOutlineUpdate }: Props) {
  const [form] = Form.useForm();
  const [outline, setOutline] = useState<PlotOutline | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [completeness, setCompleteness] = useState(0);
  
  // 新增：大纲完善任务状态管理
  const {
    setCurrentEnhancementTask,
    hasRunningEnhancementTask
  } = useGenerationStore();
  const navigate = useNavigate();
  const [isCreatingTask, setIsCreatingTask] = useState(false);
  const [enhancementTaskId, setEnhancementTaskId] = useState<string | null>(null);



  const fetchOutline = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getPlotOutline(novelId);
      setOutline(data);
      
      if (!data) {
        setLoading(false);
        return;
      }

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

  const calculateCompleteness = useCallback((mainPlot: MainPlot) => {
    const filledFields = PLOT_FIELDS.filter((field) => {
      const value = mainPlot[field.name];
      return value && String(value).trim().length > 0;
    }).length;
    const percentage = Math.round((filledFields / PLOT_FIELDS.length) * 100);
    setCompleteness(percentage);
  }, []);

  const handleAIAssist = useCallback(async (fieldName: string) => {
    const currentValues = form.getFieldsValue();

    message.loading('AI 正在生成建议...', 0);

    try {
      const result = await aiAssistOutline(novelId, {
        field_name: fieldName,
        current_context: {
          current_value: currentValues[fieldName],
          other_fields: currentValues,
        },
      });

      message.destroy();

      if (result.suggestion) {
        // 如果建议是 JSON 字符串，尝试解析
        let suggestionValue = result.suggestion;
        try {
          const parsed = JSON.parse(result.suggestion);
          suggestionValue = parsed;
        } catch {
          // 不是 JSON，保持原样
        }

        form.setFieldValue(fieldName, suggestionValue);
        message.success('AI 建议已填充');

        const updatedValues = form.getFieldsValue();
        calculateCompleteness(updatedValues as MainPlot);
      } else {
        message.warning('AI 未返回有效建议');
      }
    } catch (error) {
      message.destroy();
      console.error('AI assist error:', error);
      message.error('AI 辅助失败，请稍后重试');
    }
  }, [novelId, form, calculateCompleteness]);

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

  // 智能完善相关处理函数
  const handleSmartEnhance = useCallback(async () => {
    // 防重复点击检查
    if (hasRunningEnhancementTask() || isCreatingTask) {
      message.info('已有完善任务正在执行中，请稍后再试');
      return;
    }

    setIsCreatingTask(true);
    
    try {
      // 收集当前大纲数据
      const values = form.getFieldsValue();
      const mainPlot: MainPlot = {};
      
      PLOT_FIELDS.forEach((field) => {
        if (values[field.name]) {
          mainPlot[field.name] = values[field.name];
        }
      });

      // 创建离线任务
      interface TaskPayload {
        novel_id: string;
        task_type: 'planning' | 'writing' | 'batch_writing' | 'outline_refinement';
        input_data: Record<string, unknown>;
      }

      const taskPayload: TaskPayload = {
        novel_id: novelId,
        task_type: 'outline_refinement',
        input_data: {
          outline_data: {
            structure_type: outline?.structure_type || 'three_act',
            main_plot: mainPlot,
            sub_plots: outline?.sub_plots || [],
            key_turning_points: outline?.key_turning_points || [],
          },
          options: {
            max_iterations: 3,
            quality_threshold: 8.0,
            preserve_user_edits: true
          }
        }
      };

      const task = await createGenerationTask(taskPayload);

      // 更新全局状态
      setCurrentEnhancementTask({
        taskId: task.id,
        status: task.status,
        createdAt: new Date(task.created_at)
      });

      // 显示成功提示，提供跳转选项而非强制跳转
      message.success({
        content: '智能完善任务已创建',
        duration: 5,
      });

      // 设置本地状态以便在当前页面显示进度指示器
      setEnhancementTaskId(task.id);

    } catch (error) {
      console.error('创建完善任务失败:', error);
      message.error('创建任务失败，请稍后重试');
    } finally {
      setIsCreatingTask(false);
    }
  }, [novelId, form, outline, hasRunningEnhancementTask, isCreatingTask, setCurrentEnhancementTask, setEnhancementTaskId]);

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
      {/* 任务进度提示 */}
      {enhancementTaskId && (
        <Alert
          message="智能完善任务已创建"
          description={
            <Space>
              <span>任务正在进行中，您可以继续编辑大纲。</span>
              <Button
                type="link"
                size="small"
                onClick={() => navigate(`/novels/${novelId}?tab=generation-history`)}
              >
                查看进度
              </Button>
              <Button
                type="link"
                size="small"
                onClick={() => setEnhancementTaskId(null)}
              >
                关闭提示
              </Button>
            </Space>
          }
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      <Card style={{ marginBottom: 16 }}>
        <Row align="middle" gutter={16}>
          <Col flex="auto">
            <Space orientation="vertical" size="small" style={{ width: '100%' }}>
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
                icon={<ThunderboltOutlined />}
                onClick={handleSmartEnhance}
                disabled={hasRunningEnhancementTask() || isCreatingTask}
                loading={isCreatingTask}
              >
                {isCreatingTask ? '创建中...' : '智能完善'}
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

      {/* 使用标签页组织内容 */}
      <Tabs
        defaultActiveKey="main-plot"
        items={[
          {
            key: 'main-plot',
            label: (
              <Space>
                <ProfileOutlined />
                主线剧情
              </Space>
            ),
            children: (
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
            ),
          },
          {
            key: 'volumes',
            label: (
              <Space>
                <BookOutlined />
                卷章结构
                {outline?.volumes && outline.volumes.length > 0 && (
                  <Tag color="blue">{outline.volumes.length}卷</Tag>
                )}
              </Space>
            ),
            children: <VolumeStructurePanel outline={outline} />,
          },
        ]}
      />

      <Divider />

      <Card
        size="small"
        title="操作提示"
        type="inner"
      >
        <Typography.Paragraph style={{ margin: 0 }}>
          <Typography.Text type="secondary">
            💡 建议按顺序填写各要素，AI 辅助会根据已有内容提供更精准的建议。
            完成度达到 80% 以上即可确认大纲。
            <br />
            💡 使用「智能完善」功能可以自动生成详细的卷章结构和剧情设计。
          </Typography.Text>
        </Typography.Paragraph>
      </Card>
    </div>
  );
}
