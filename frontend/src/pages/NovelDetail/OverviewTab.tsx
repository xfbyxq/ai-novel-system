import { useState, useEffect } from 'react';
import {
  Card, Row, Col, Statistic, Button, Space, Modal, InputNumber, Input, Select, Form, message, Typography,
} from 'antd';
import {
  FileTextOutlined, TeamOutlined, DollarOutlined, RocketOutlined, EditOutlined, SettingOutlined,
} from '@ant-design/icons';
import type { Novel } from '@/api/types';
import { updateNovel } from '@/api/novels';
import { createGenerationTask } from '@/api/generation';
import { useGenerationStore } from '@/stores/useGenerationStore';
import { formatWordCount, formatCost } from '@/utils/format';
import { GENRE_OPTIONS, NOVEL_STATUS_MAP } from '@/utils/constants';

interface Props {
  novel: Novel;
  onRefresh: () => void;
}

export default function OverviewTab({ novel, onRefresh }: Props) {
  const [planningLoading, setPlanningLoading] = useState(false);
  const [writingModalOpen, setWritingModalOpen] = useState(false);
  const { tasks, fetchTasks } = useGenerationStore();

  useEffect(() => {
    void fetchTasks(novel.id);
  }, [novel.id, fetchTasks]);

  const hasRunningPlanningTask = tasks.some(
    t => t.task_type === 'planning' && (t.status === 'pending' || t.status === 'running')
  );
  const [chapterNum, setChapterNum] = useState(1);
  const [writingLoading, setWritingLoading] = useState(false);
  // 批量生成状态
  const [batchModalOpen, setBatchModalOpen] = useState(false);
  const [fromChapter, setFromChapter] = useState(1);
  const [toChapter, setToChapter] = useState(5);
  const [batchLoading, setBatchLoading] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editLoading, setEditLoading] = useState(false);
  const [editForm] = Form.useForm();

  const handleStartPlanning = async () => {
    setPlanningLoading(true);
    try {
      await createGenerationTask({ novel_id: novel.id, task_type: 'planning' });
      message.success('企划任务已创建，请在"生成历史"中查看进度');
      void fetchTasks(novel.id);
      onRefresh();
    } finally {
      setPlanningLoading(false);
    }
  };

  const handleStartWriting = async () => {
    setWritingLoading(true);
    try {
      await createGenerationTask({
        novel_id: novel.id,
        task_type: 'writing',
        input_data: { chapter_number: chapterNum, volume_number: 1 },
      });
      message.success(`第 ${chapterNum} 章写作任务已创建`);
      setWritingModalOpen(false);
      onRefresh();
    } finally {
      setWritingLoading(false);
    }
  };

  const handleBatchWriting = async () => {
    setBatchLoading(true);
    try {
      await createGenerationTask({
        novel_id: novel.id,
        task_type: 'batch_writing',
        from_chapter: fromChapter,
        to_chapter: toChapter,
        volume_number: 1,
      });
      message.success(`批量生成任务已创建（第 ${fromChapter}-${toChapter} 章）`);
      setBatchModalOpen(false);
      onRefresh();
    } finally {
      setBatchLoading(false);
    }
  };

  const handleOpenEdit = () => {
    editForm.setFieldsValue({
      title: novel.title,
      genre: novel.genre,
      tags: novel.tags || [],
      synopsis: novel.synopsis || '',
      status: novel.status,
      target_platform: novel.target_platform || '',
    });
    setEditOpen(true);
  };

  const handleSaveEdit = async () => {
    setEditLoading(true);
    try {
      const values = await editForm.validateFields();
      await updateNovel(novel.id, values);
      message.success('小说信息已更新');
      setEditOpen(false);
      onRefresh();
    } finally {
      setEditLoading(false);
    }
  };

  return (
    <div>
      {novel.synopsis && (
        <Card style={{ marginBottom: 16 }}>
          <Typography.Title level={5}>简介</Typography.Title>
          <Typography.Paragraph>{novel.synopsis}</Typography.Paragraph>
        </Card>
      )}

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}>
          <Card><Statistic title="总字数" value={formatWordCount(novel.word_count)} prefix={<FileTextOutlined />} /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card><Statistic title="章节数" value={novel.chapter_count} prefix={<EditOutlined />} /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card><Statistic title="Token成本" value={formatCost(novel.token_cost)} prefix={<DollarOutlined />} /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card><Statistic title="目标平台" value={novel.target_platform} prefix={<TeamOutlined />} /></Card>
        </Col>
      </Row>

      <Card title="快速操作">
        <Space>
          <Button
            type="primary"
            icon={<RocketOutlined />}
            loading={planningLoading}
            onClick={handleStartPlanning}
            disabled={novel.status !== 'planning' || hasRunningPlanningTask}
          >
            开始企划
          </Button>
          <Button
            icon={<EditOutlined />}
            onClick={() => {
              setChapterNum((novel.chapter_count || 0) + 1);
              setWritingModalOpen(true);
            }}
            disabled={novel.status === 'planning'}
          >
            生成单章
          </Button>
          <Button
            type="primary"
            icon={<EditOutlined />}
            onClick={() => {
              const nextChapter = (novel.chapter_count || 0) + 1;
              setFromChapter(nextChapter);
              setToChapter(nextChapter + 4);
              setBatchModalOpen(true);
            }}
            disabled={novel.status === 'planning'}
          >
            批量生成章节
          </Button>
          <Button
            icon={<SettingOutlined />}
            onClick={handleOpenEdit}
          >
            编辑小说
          </Button>
        </Space>
      </Card>

      <Modal
        title="生成单章"
        open={writingModalOpen}
        onOk={handleStartWriting}
        confirmLoading={writingLoading}
        onCancel={() => setWritingModalOpen(false)}
        okText="开始写作"
      >
        <Space orientation="vertical" style={{ width: '100%' }}>
          <Typography.Text>请输入要生成的章节号：</Typography.Text>
          <InputNumber
            min={1}
            value={chapterNum}
            onChange={(v) => v && setChapterNum(v)}
            style={{ width: '100%' }}
          />
        </Space>
      </Modal>

      <Modal
        title="批量生成章节"
        open={batchModalOpen}
        onOk={handleBatchWriting}
        confirmLoading={batchLoading}
        onCancel={() => setBatchModalOpen(false)}
        okText="开始批量生成"
        width={500}
      >
        <Space orientation="vertical" style={{ width: '100%' }} size="large">
          <div>
            <Typography.Text strong>章节范围：</Typography.Text>
            <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <InputNumber
                min={1}
                value={fromChapter}
                onChange={(v) => v && setFromChapter(v)}
                style={{ flex: 1 }}
                placeholder="起始章节"
              />
              <Typography.Text>至</Typography.Text>
              <InputNumber
                min={fromChapter}
                value={toChapter}
                onChange={(v) => v && setToChapter(v)}
                style={{ flex: 1 }}
                placeholder="结束章节"
              />
            </div>
          </div>
          <Typography.Text type="secondary">
            将生成第 {fromChapter} 至第 {toChapter} 章，共 {toChapter - fromChapter + 1} 章
          </Typography.Text>
          <Typography.Text type="warning">
            注意：批量生成需要较长时间，请在“生成历史”中查看进度
          </Typography.Text>
        </Space>
      </Modal>

      <Modal
        title="编辑小说"
        open={editOpen}
        onOk={handleSaveEdit}
        confirmLoading={editLoading}
        onCancel={() => setEditOpen(false)}
        okText="保存"
        width={600}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="genre" label="类型" rules={[{ required: true, message: '请选择类型' }]}>
            <Select options={GENRE_OPTIONS.map((g) => ({ value: g, label: g }))} />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Select mode="tags" placeholder="输入标签后回车" />
          </Form.Item>
          <Form.Item name="synopsis" label="简介">
            <Input.TextArea rows={4} placeholder="简要描述小说的核心设定和故事主线" />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select options={Object.entries(NOVEL_STATUS_MAP).map(([value, item]) => ({ value, label: item.label }))} />
          </Form.Item>
          <Form.Item name="target_platform" label="目标平台">
            <Input placeholder="如：起点中文网" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
