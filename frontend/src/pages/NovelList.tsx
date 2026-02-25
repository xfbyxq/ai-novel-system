import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Typography, Table, Button, Space, Select, Modal, Form, Input, message,
} from 'antd';
import { PlusOutlined, DeleteOutlined, EyeOutlined, RobotOutlined } from '@ant-design/icons';
import type { Novel, NovelCreate } from '@/api/types';
import { getNovels, createNovel, deleteNovel } from '@/api/novels';
import StatusBadge from '@/components/StatusBadge';
import AIChatDrawer from '@/components/AIChatDrawer';
import { formatWordCount, formatDate, formatCost } from '@/utils/format';
import { GENRE_OPTIONS, NOVEL_STATUS_MAP } from '@/utils/constants';

export default function NovelList() {
  const navigate = useNavigate();
  const [novels, setNovels] = useState<Novel[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [aiChatOpen, setAiChatOpen] = useState(false);
  const [form] = Form.useForm<NovelCreate>();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getNovels(page, 10, statusFilter);
      setNovels(res.items);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter]);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      setCreating(true);
      const novel = await createNovel(values);
      message.success('小说创建成功');
      setModalOpen(false);
      form.resetFields();
      navigate(`/novels/${novel.id}`);
    } catch {
      // validation error, do nothing
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string, title: string) => {
    Modal.confirm({
      title: `确认删除「${title}」？`,
      content: '删除后不可恢复，所有章节和生成数据都将一并删除。',
      okText: '删除',
      okType: 'danger',
      onOk: async () => {
        await deleteNovel(id);
        message.success('已删除');
        load();
      },
    });
  };

  return (
    <div>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Typography.Title level={4} style={{ margin: 0 }}>小说管理</Typography.Title>
        <Space>
          <Select
            allowClear
            placeholder="状态筛选"
            style={{ width: 120 }}
            value={statusFilter}
            onChange={(v) => { setStatusFilter(v); setPage(1); }}
            options={Object.entries(NOVEL_STATUS_MAP).map(([k, v]) => ({ value: k, label: v.label }))}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            创建小说
          </Button>
          <Button icon={<RobotOutlined />} onClick={() => setAiChatOpen(true)}>
            AI 辅助
          </Button>
        </Space>
      </Space>

      <Table
        dataSource={novels}
        rowKey="id"
        loading={loading}
        pagination={{
          current: page,
          pageSize: 10,
          total,
          onChange: setPage,
          showTotal: (t) => `共 ${t} 部`,
        }}
        columns={[
          { title: '标题', dataIndex: 'title', render: (v: string, r: Novel) => (
            <a onClick={() => navigate(`/novels/${r.id}`)}>{v}</a>
          )},
          { title: '类型', dataIndex: 'genre', width: 80 },
          { title: '状态', dataIndex: 'status', width: 100, render: (v: string) => <StatusBadge type="novel" status={v} /> },
          { title: '字数', dataIndex: 'word_count', width: 100, render: formatWordCount },
          { title: '章节', dataIndex: 'chapter_count', width: 60 },
          { title: 'Token成本', dataIndex: 'token_cost', width: 100, render: formatCost },
          { title: '创建时间', dataIndex: 'created_at', width: 160, render: formatDate },
          {
            title: '操作', width: 120, render: (_: unknown, r: Novel) => (
              <Space>
                <Button size="small" icon={<EyeOutlined />} onClick={() => navigate(`/novels/${r.id}`)} />
                <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id, r.title)} />
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title="创建新小说"
        open={modalOpen}
        onOk={handleCreate}
        confirmLoading={creating}
        onCancel={() => { setModalOpen(false); form.resetFields(); }}
        okText="创建"
      >
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}>
            <Input placeholder="例如：星辰大主宰" />
          </Form.Item>
          <Form.Item name="genre" label="类型" rules={[{ required: true, message: '请选择类型' }]}>
            <Select placeholder="选择类型" options={GENRE_OPTIONS.map((g) => ({ value: g, label: g }))} />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Select mode="tags" placeholder="输入标签后回车" />
          </Form.Item>
          <Form.Item name="synopsis" label="简介">
            <Input.TextArea rows={3} placeholder="简要描述小说的核心设定和故事主线" />
          </Form.Item>
          <Form.Item name="length_type" label="篇幅类型" initialValue="medium">
            <Select placeholder="选择篇幅类型" options={[
              { value: 'short', label: '短文' },
              { value: 'medium', label: '中篇小说' },
              { value: 'long', label: '长篇小说' }
            ]} />
          </Form.Item>
        </Form>
      </Modal>

      <AIChatDrawer
        open={aiChatOpen}
        onClose={() => setAiChatOpen(false)}
        scene="novel_creation"
      />
    </div>
  );
}
