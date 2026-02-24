import { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Modal,
  Form,
  Input,
  Select,
  message,
  Descriptions,
  Progress,
  Typography,
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  StopOutlined,
  EyeOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { CrawlerTask, CrawlerTaskCreate, CrawlType } from '@/api/types';
import {
  getCrawlerTasks,
  createCrawlerTask,
  cancelCrawlerTask,
  getCrawlerTask,
} from '@/api/crawler';
import AIChatDrawer from '@/components/AIChatDrawer';

const { Text } = Typography;

const crawlTypeOptions: { value: CrawlType; label: string }[] = [
  { value: 'ranking', label: '排行榜' },
  { value: 'trending_tags', label: '热门标签' },
  { value: 'book_metadata', label: '书籍详情' },
  { value: 'genre_list', label: '分类列表' },
];

const platformOptions = [
  { value: 'qidian', label: '起点中文网' },
  { value: 'douyin', label: '抖音' },
  { value: 'fanqie', label: '番茄小说' },
  { value: 'zongheng', label: '纵横中文网' },
];

const rankingTypeOptions = [
  { value: 'yuepiao', label: '月票榜' },
  { value: 'hotsales', label: '畅销榜' },
  { value: 'readIndex', label: '阅读指数榜' },
  { value: 'recom', label: '推荐榜' },
  { value: 'collect', label: '收藏榜' },
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

export default function CrawlerTasks() {
  const [tasks, setTasks] = useState<CrawlerTask[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<CrawlerTask | null>(null);
  const [aiChatOpen, setAiChatOpen] = useState(false);
  const [form] = Form.useForm();
  const [selectedCrawlType, setSelectedCrawlType] = useState<CrawlType>('ranking');

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const res = await getCrawlerTasks({ page, page_size: pageSize });
      setTasks(res.items);
      setTotal(res.total);
    } catch (err) {
      message.error('加载任务列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
  }, [page, pageSize]);

  // 轮询运行中的任务
  useEffect(() => {
    const runningTasks = tasks.filter((t) => t.status === 'running');
    if (runningTasks.length === 0) return;

    const interval = setInterval(fetchTasks, 3000);
    return () => clearInterval(interval);
  }, [tasks]);

  const handleCreate = async (values: CrawlerTaskCreate & { ranking_type?: string; book_ids?: string }) => {
    try {
      const config: Record<string, unknown> = {};
      if (values.crawl_type === 'ranking' && values.ranking_type) {
        config.ranking_type = values.ranking_type;
        config.max_pages = 3;
      }
      if (values.crawl_type === 'book_metadata' && values.book_ids) {
        config.book_ids = values.book_ids.split(',').map((id) => id.trim());
      }

      await createCrawlerTask({
        task_name: values.task_name,
        platform: values.platform,
        crawl_type: values.crawl_type,
        config: Object.keys(config).length > 0 ? config : undefined,
      });
      message.success('任务创建成功，已开始执行');
      setCreateModalOpen(false);
      form.resetFields();
      fetchTasks();
    } catch (err) {
      message.error('创建任务失败');
    }
  };

  const handleCancel = async (taskId: string) => {
    try {
      await cancelCrawlerTask(taskId);
      message.success('任务已取消');
      fetchTasks();
    } catch (err) {
      message.error('取消任务失败');
    }
  };

  const handleViewDetail = async (taskId: string) => {
    try {
      const task = await getCrawlerTask(taskId);
      setSelectedTask(task);
      setDetailModalOpen(true);
    } catch (err) {
      message.error('获取任务详情失败');
    }
  };

  const columns: ColumnsType<CrawlerTask> = [
    {
      title: '任务名称',
      dataIndex: 'task_name',
      key: 'task_name',
      width: 200,
    },
    {
      title: '平台',
      dataIndex: 'platform',
      key: 'platform',
      width: 100,
      render: (v) => v === 'qidian' ? '起点中文网' : v,
    },
    {
      title: '爬取类型',
      dataIndex: 'crawl_type',
      key: 'crawl_type',
      width: 120,
      render: (v) => crawlTypeOptions.find((o) => o.value === v)?.label || v,
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
          const { current_page, total_pages, items_crawled } = record.progress as {
            current_page?: number;
            total_pages?: number;
            items_crawled?: number;
          };
          if (current_page && total_pages) {
            return (
              <Space orientation="vertical" size={0}>
                <Progress
                  percent={Math.round((current_page / total_pages) * 100)}
                  size="small"
                  status="active"
                />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  已爬取 {items_crawled || 0} 条
                </Text>
              </Space>
            );
          }
          return <Text type="secondary">执行中...</Text>;
        }
        if (record.status === 'completed' && record.result_summary) {
          const { items_count } = record.result_summary as { items_count?: number };
          return <Text type="success">共 {items_count || 0} 条数据</Text>;
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
        title="爬虫任务管理"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={fetchTasks}>
              刷新
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalOpen(true)}
            >
              新建任务
            </Button>
            <Button icon={<RobotOutlined />} onClick={() => setAiChatOpen(true)}>
              AI 辅助
            </Button>
          </Space>
        }
      >
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
      </Card>

      {/* 创建任务弹窗 */}
      <Modal
        title="新建爬虫任务"
        open={createModalOpen}
        onCancel={() => {
          setCreateModalOpen(false);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        okText="创建"
        cancelText="取消"
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreate}
          initialValues={{ platform: 'qidian', crawl_type: 'ranking', ranking_type: 'yuepiao' }}
        >
          <Form.Item
            name="task_name"
            label="任务名称"
            rules={[{ required: true, message: '请输入任务名称' }]}
          >
            <Input placeholder="例如：起点月票榜爬取" />
          </Form.Item>
          <Form.Item
            name="platform"
            label="平台"
            rules={[{ required: true }]}
          >
            <Select options={platformOptions} />
          </Form.Item>
          <Form.Item
            name="crawl_type"
            label="爬取类型"
            rules={[{ required: true }]}
          >
            <Select
              options={crawlTypeOptions}
              onChange={(v) => setSelectedCrawlType(v)}
            />
          </Form.Item>
          {selectedCrawlType === 'ranking' && (
            <Form.Item name="ranking_type" label="排行榜类型">
              <Select options={rankingTypeOptions} />
            </Form.Item>
          )}
          {selectedCrawlType === 'book_metadata' && (
            <Form.Item
              name="book_ids"
              label="书籍ID列表"
              rules={[{ required: true, message: '请输入书籍ID' }]}
              extra="多个ID用逗号分隔"
            >
              <Input.TextArea placeholder="例如：1234567,2345678,3456789" />
            </Form.Item>
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
            <Descriptions.Item label="任务名称" span={2}>
              {selectedTask.task_name}
            </Descriptions.Item>
            <Descriptions.Item label="平台">
              {selectedTask.platform === 'qidian' ? '起点中文网' : selectedTask.platform}
            </Descriptions.Item>
            <Descriptions.Item label="爬取类型">
              {crawlTypeOptions.find((o) => o.value === selectedTask.crawl_type)?.label}
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={statusColorMap[selectedTask.status]}>
                {statusTextMap[selectedTask.status]}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">
              {new Date(selectedTask.created_at).toLocaleString('zh-CN')}
            </Descriptions.Item>
            {selectedTask.started_at && (
              <Descriptions.Item label="开始时间">
                {new Date(selectedTask.started_at).toLocaleString('zh-CN')}
              </Descriptions.Item>
            )}
            {selectedTask.completed_at && (
              <Descriptions.Item label="完成时间">
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

      <AIChatDrawer
        open={aiChatOpen}
        onClose={() => setAiChatOpen(false)}
        scene="crawler_task"
      />
    </div>
  );
}
