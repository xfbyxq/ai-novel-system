import { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Modal,
  Form,
  Select,
  InputNumber,
  message,
  Descriptions,
  Progress,
  Typography,
  Empty,
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  StopOutlined,
  EyeOutlined,
  SendOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { PublishTask, PublishTaskCreate, PlatformAccount, Novel, PublishType } from '@/api/types';
import {
  getPublishTasks,
  createPublishTask,
  cancelPublishTask,
  getPublishTask,
  getPlatformAccounts,
} from '@/api/publishing';
import { getNovels } from '@/api/novels';

const { Text } = Typography;

const publishTypeOptions: { value: PublishType; label: string }[] = [
  { value: 'create_book', label: '创建新书' },
  { value: 'publish_chapter', label: '发布单章' },
  { value: 'batch_publish', label: '批量发布' },
];

const statusColorMap: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
  cancelled: 'warning',
};

const statusTextMap: Record<string, string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

export default function PublishTasks() {
  const [tasks, setTasks] = useState<PublishTask[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<PublishTask | null>(null);
  const [accounts, setAccounts] = useState<PlatformAccount[]>([]);
  const [novels, setNovels] = useState<Novel[]>([]);
  const [selectedPublishType, setSelectedPublishType] = useState<PublishType>('create_book');
  const [form] = Form.useForm();

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const res = await getPublishTasks({ page, page_size: pageSize });
      setTasks(res.items);
      setTotal(res.total);
    } catch (err) {
      message.error('加载任务列表失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchAccounts = async () => {
    try {
      const res = await getPlatformAccounts({ status: 'active', page_size: 100 });
      setAccounts(res.items);
    } catch {
      // Silent fail
    }
  };

  const fetchNovels = async () => {
    try {
      const res = await getNovels(1, 100);
      setNovels(res.items);
    } catch {
      // Silent fail
    }
  };

  useEffect(() => {
    fetchTasks();
  }, [page, pageSize]);

  useEffect(() => {
    fetchAccounts();
    fetchNovels();
  }, []);

  // 轮询运行中的任务
  useEffect(() => {
    const runningTasks = tasks.filter((t) => t.status === 'running');
    if (runningTasks.length === 0) return;

    const interval = setInterval(fetchTasks, 3000);
    return () => clearInterval(interval);
  }, [tasks]);

  const handleCreate = async (values: PublishTaskCreate & { from_chapter?: number; to_chapter?: number }) => {
    try {
      const config: Record<string, unknown> = {};
      if (values.publish_type === 'publish_chapter' && values.from_chapter) {
        config.chapter_number = values.from_chapter;
      }

      await createPublishTask({
        novel_id: values.novel_id,
        account_id: values.account_id,
        publish_type: values.publish_type,
        config: Object.keys(config).length > 0 ? config : undefined,
        from_chapter: values.publish_type === 'batch_publish' ? values.from_chapter : undefined,
        to_chapter: values.publish_type === 'batch_publish' ? values.to_chapter : undefined,
      });
      message.success('发布任务创建成功');
      setCreateModalOpen(false);
      form.resetFields();
      fetchTasks();
    } catch (err) {
      message.error('创建任务失败');
    }
  };

  const handleCancel = async (taskId: string) => {
    try {
      await cancelPublishTask(taskId);
      message.success('任务已取消');
      fetchTasks();
    } catch (err) {
      message.error('取消任务失败');
    }
  };

  const handleViewDetail = async (taskId: string) => {
    try {
      const task = await getPublishTask(taskId);
      setSelectedTask(task);
      setDetailModalOpen(true);
    } catch (err) {
      message.error('获取任务详情失败');
    }
  };

  const columns: ColumnsType<PublishTask> = [
    {
      title: '发布类型',
      dataIndex: 'publish_type',
      key: 'publish_type',
      width: 120,
      render: (v) => publishTypeOptions.find((o) => o.value === v)?.label || v,
    },
    {
      title: '小说ID',
      dataIndex: 'novel_id',
      key: 'novel_id',
      width: 120,
      render: (v) => <Text copyable={{ text: v }}>{v.slice(0, 8)}...</Text>,
    },
    {
      title: '平台书籍ID',
      dataIndex: 'platform_book_id',
      key: 'platform_book_id',
      width: 130,
      render: (v) => v ? <Text copyable={{ text: v }}>{v}</Text> : '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={statusColorMap[status]}>{statusTextMap[status] || status}</Tag>
      ),
    },
    {
      title: '进度',
      key: 'progress',
      width: 180,
      render: (_, record) => {
        if (record.status === 'running' && record.progress) {
          const { current, total: progressTotal } = record.progress as {
            current?: number;
            total?: number;
          };
          if (current && progressTotal) {
            return (
              <Progress
                percent={Math.round((current / progressTotal) * 100)}
                size="small"
                status="active"
              />
            );
          }
          return <Text type="secondary">执行中...</Text>;
        }
        if (record.status === 'completed' && record.result_summary) {
          const { success_count, total: resultTotal } = record.result_summary as {
            success_count?: number;
            total?: number;
          };
          if (resultTotal) {
            return <Text type="success">{success_count}/{resultTotal} 成功</Text>;
          }
          return <Text type="success">完成</Text>;
        }
        return '-';
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (v) => new Date(v).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetail(record.id)}
          >
            详情
          </Button>
          {record.status === 'running' && (
            <Button
              type="link"
              size="small"
              danger
              icon={<StopOutlined />}
              onClick={() => handleCancel(record.id)}
            >
              取消
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        title={
          <Space>
            <SendOutlined />
            发布任务管理
          </Space>
        }
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={fetchTasks}>
              刷新
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalOpen(true)}
              disabled={accounts.length === 0}
            >
              新建任务
            </Button>
          </Space>
        }
      >
        {accounts.length === 0 ? (
          <Empty
            description="请先添加平台账号"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        ) : (
          <Table
            columns={columns}
            dataSource={tasks}
            rowKey="id"
            loading={loading}
            pagination={{
              current: page,
              pageSize,
              total,
              showSizeChanger: true,
              showTotal: (t) => `共 ${t} 条`,
              onChange: (p, ps) => {
                setPage(p);
                setPageSize(ps);
              },
            }}
          />
        )}
      </Card>

      {/* 创建任务弹窗 */}
      <Modal
        title="新建发布任务"
        open={createModalOpen}
        onCancel={() => {
          setCreateModalOpen(false);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        okText="创建"
        cancelText="取消"
        width={500}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreate}
          initialValues={{ publish_type: 'create_book' }}
        >
          <Form.Item
            name="novel_id"
            label="选择小说"
            rules={[{ required: true, message: '请选择小说' }]}
          >
            <Select
              placeholder="选择要发布的小说"
              showSearch
              optionFilterProp="label"
              options={novels.map((n) => ({
                value: n.id,
                label: `${n.title} (${n.chapter_count}章)`,
              }))}
            />
          </Form.Item>
          <Form.Item
            name="account_id"
            label="发布账号"
            rules={[{ required: true, message: '请选择账号' }]}
          >
            <Select
              placeholder="选择发布账号"
              options={accounts.map((a) => ({
                value: a.id,
                label: `${a.account_name} (${a.username})`,
              }))}
            />
          </Form.Item>
          <Form.Item
            name="publish_type"
            label="发布类型"
            rules={[{ required: true }]}
          >
            <Select
              options={publishTypeOptions}
              onChange={(v) => setSelectedPublishType(v)}
            />
          </Form.Item>
          {selectedPublishType === 'publish_chapter' && (
            <Form.Item
              name="from_chapter"
              label="章节号"
              rules={[{ required: true, message: '请输入章节号' }]}
            >
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
          )}
          {selectedPublishType === 'batch_publish' && (
            <Space style={{ width: '100%' }}>
              <Form.Item
                name="from_chapter"
                label="起始章节"
                rules={[{ required: true, message: '请输入' }]}
                style={{ marginBottom: 0 }}
              >
                <InputNumber min={1} />
              </Form.Item>
              <Form.Item
                name="to_chapter"
                label="结束章节"
                rules={[{ required: true, message: '请输入' }]}
                style={{ marginBottom: 0 }}
              >
                <InputNumber min={1} />
              </Form.Item>
            </Space>
          )}
        </Form>
      </Modal>

      {/* 任务详情弹窗 */}
      <Modal
        title="任务详情"
        open={detailModalOpen}
        onCancel={() => setDetailModalOpen(false)}
        footer={null}
        width={600}
      >
        {selectedTask && (
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="发布类型">
              {publishTypeOptions.find((o) => o.value === selectedTask.publish_type)?.label}
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={statusColorMap[selectedTask.status]}>
                {statusTextMap[selectedTask.status]}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="小说ID" span={2}>
              <Text copyable>{selectedTask.novel_id}</Text>
            </Descriptions.Item>
            {selectedTask.platform_book_id && (
              <Descriptions.Item label="平台书籍ID" span={2}>
                <Text copyable>{selectedTask.platform_book_id}</Text>
              </Descriptions.Item>
            )}
            <Descriptions.Item label="创建时间">
              {new Date(selectedTask.created_at).toLocaleString('zh-CN')}
            </Descriptions.Item>
            {selectedTask.started_at && (
              <Descriptions.Item label="开始时间">
                {new Date(selectedTask.started_at).toLocaleString('zh-CN')}
              </Descriptions.Item>
            )}
            {selectedTask.completed_at && (
              <Descriptions.Item label="完成时间" span={2}>
                {new Date(selectedTask.completed_at).toLocaleString('zh-CN')}
              </Descriptions.Item>
            )}
            {selectedTask.result_summary && (
              <Descriptions.Item label="结果摘要" span={2}>
                <pre style={{ margin: 0, fontSize: 12 }}>
                  {JSON.stringify(selectedTask.result_summary, null, 2)}
                </pre>
              </Descriptions.Item>
            )}
            {selectedTask.error_message && (
              <Descriptions.Item label="错误信息" span={2}>
                <Text type="danger">{selectedTask.error_message}</Text>
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Modal>
    </div>
  );
}
