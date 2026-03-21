import { Modal, Typography, Tag, Space, Divider, Row, Col, Card, Badge } from 'antd';
import {
  CheckCircleOutlined,
  MinusCircleOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
  SmileOutlined,
  FrownOutlined,
} from '@ant-design/icons';

export interface ChapterTask {
  chapter_number: number;
  title?: string;
  mandatory_events?: string[];
  optional_events?: string[];
  foreshadowing_tasks?: string[];
  emotional_tone?: string;
  tension_position?: string;
  word_count_target?: number;
}

interface ChapterOutlineTaskModalProps {
  open: boolean;
  task: ChapterTask | null;
  onConfirm?: () => void;
  onCancel?: () => void;
}

export default function ChapterOutlineTaskModal({
  open,
  task,
  onConfirm,
  onCancel,
}: ChapterOutlineTaskModalProps) {
  if (!task) return null;

  const getEmotionalToneIcon = (tone?: string) => {
    if (!tone) return <ClockCircleOutlined />;
    const positiveTones = ['happy', 'exciting', 'hopeful', 'triumphant'];
    const negativeTones = ['sad', 'tense', 'angry', 'fearful'];
    
    if (positiveTones.some((t) => tone.toLowerCase().includes(t))) {
      return <SmileOutlined style={{ color: '#52c41a' }} />;
    }
    if (negativeTones.some((t) => tone.toLowerCase().includes(t))) {
      return <FrownOutlined style={{ color: '#ff4d4f' }} />;
    }
    return <ClockCircleOutlined />;
  };

  const getTensionColor = (position?: string) => {
    if (!position) return 'default';
    const pos = position.toLowerCase();
    if (pos.includes('high') || pos.includes('climax')) return 'red';
    if (pos.includes('medium') || pos.includes('rising')) return 'orange';
    if (pos.includes('low') || pos.includes('calm')) return 'green';
    return 'blue';
  };

  return (
    <Modal
      open={open}
      title={
        <Space>
          <ThunderboltOutlined />
          <Typography.Text strong>
            第{task.chapter_number}章：{task.title || '未命名'}
          </Typography.Text>
        </Space>
      }
      onConfirm={onConfirm}
      onCancel={onCancel}
      okText="我已了解本章任务"
      okButtonProps={{ size: 'large' }}
      width={700}
      footer={[
        <Button key="cancel" onClick={onCancel}>
          稍后再说
        </Button>,
        <Button key="confirm" type="primary" onClick={onConfirm} size="large">
          我已了解本章任务
        </Button>,
      ]}
    >
      <div style={{ maxHeight: '60vh', overflowY: 'auto' }}>
        <Row gutter={[16, 16]}>
          <Col span={12}>
            <Card size="small" title="情感基调" type="inner">
              <Space>
                {getEmotionalToneIcon(task.emotional_tone)}
                <Typography.Text>
                  {task.emotional_tone || '未指定'}
                </Typography.Text>
              </Space>
            </Card>
          </Col>

          <Col span={12}>
            <Card size="small" title="张力位置" type="inner">
              <Space>
                <Badge
                  color={getTensionColor(task.tension_position) as string}
                  text={task.tension_position || '未指定'}
                />
              </Space>
            </Card>
          </Col>
        </Row>

        {task.word_count_target && (
          <Card size="small" type="inner" style={{ marginTop: 16 }}>
            <Space>
              <Typography.Text type="secondary">目标字数：</Typography.Text>
              <Typography.Text strong>{task.word_count_target}</Typography.Text>
            </Space>
          </Card>
        )}

        <Divider orientation="left">强制性事件</Divider>

        {task.mandatory_events && task.mandatory_events.length > 0 ? (
          <Card type="inner" size="small">
            <Space orientation="vertical" size="small" style={{ width: '100%' }}>
              {task.mandatory_events.map((event, index) => (
                <Space key={index} align="start">
                  <CheckCircleOutlined style={{ color: '#52c41a', marginTop: 4 }} />
                  <Typography.Paragraph style={{ margin: 0 }}>
                    {event}
                  </Typography.Paragraph>
                </Space>
              ))}
            </Space>
          </Card>
        ) : (
          <Typography.Text type="secondary">无强制性事件</Typography.Text>
        )}

        <Divider orientation="left" orientationMargin="0">可选事件</Divider>

        {task.optional_events && task.optional_events.length > 0 ? (
          <Card type="inner" size="small">
            <Space orientation="vertical" size="small" style={{ width: '100%' }}>
              {task.optional_events.map((event, index) => (
                <Space key={index} align="start">
                  <MinusCircleOutlined style={{ color: '#1890ff', marginTop: 4 }} />
                  <Typography.Paragraph style={{ margin: 0 }}>
                    {event}
                  </Typography.Paragraph>
                </Space>
              ))}
            </Space>
          </Card>
        ) : (
          <Typography.Text type="secondary">无可选事件</Typography.Text>
        )}

        <Divider orientation="left">伏笔任务</Divider>

        {task.foreshadowing_tasks && task.foreshadowing_tasks.length > 0 ? (
          <Card type="inner" size="small">
            <Space orientation="vertical" size="small" style={{ width: '100%' }}>
              {task.foreshadowing_tasks.map((task, index) => (
                <Space key={index} align="start">
                  <ClockCircleOutlined style={{ color: '#faad14', marginTop: 4 }} />
                  <Typography.Paragraph style={{ margin: 0 }}>
                    {task}
                  </Typography.Paragraph>
                </Space>
              ))}
            </Space>
          </Card>
        ) : (
          <Typography.Text type="secondary">无伏笔任务</Typography.Text>
        )}
      </div>
    </Modal>
  );
}

import { Button } from 'antd';
