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
  message,
  Popconfirm,
  Typography,
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  DeleteOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { PlatformAccount, PlatformAccountCreate } from '@/api/types';
import {
  getPlatformAccounts,
  createPlatformAccount,
  deletePlatformAccount,
  verifyPlatformAccount,
} from '@/api/publishing';

const { Text } = Typography;

const statusColorMap: Record<string, string> = {
  active: 'success',
  inactive: 'default',
  invalid: 'error',
  suspended: 'warning',
};

const statusTextMap: Record<string, string> = {
  active: '正常',
  inactive: '未激活',
  invalid: '无效',
  suspended: '已暂停',
};

export default function PlatformAccounts() {
  const [accounts, setAccounts] = useState<PlatformAccount[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [verifying, setVerifying] = useState<string | null>(null);
  const [form] = Form.useForm();

  const fetchAccounts = async () => {
    setLoading(true);
    try {
      const res = await getPlatformAccounts({ page, page_size: pageSize });
      setAccounts(res.items);
      setTotal(res.total);
    } catch (err) {
      message.error('加载账号列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAccounts();
  }, [page, pageSize]);

  const handleCreate = async (values: PlatformAccountCreate) => {
    try {
      await createPlatformAccount({
        ...values,
        platform: 'qidian',
      });
      message.success('账号创建成功');
      setCreateModalOpen(false);
      form.resetFields();
      fetchAccounts();
    } catch (err) {
      message.error('创建账号失败');
    }
  };

  const handleDelete = async (accountId: string) => {
    try {
      await deletePlatformAccount(accountId);
      message.success('账号已删除');
      fetchAccounts();
    } catch (err) {
      message.error('删除账号失败');
    }
  };

  const handleVerify = async (accountId: string) => {
    setVerifying(accountId);
    try {
      const result = await verifyPlatformAccount(accountId);
      if (result.success) {
        message.success('账号验证成功');
      } else {
        message.warning('账号验证失败');
      }
      fetchAccounts();
    } catch (err) {
      message.error('验证请求失败');
    } finally {
      setVerifying(null);
    }
  };

  const columns: ColumnsType<PlatformAccount> = [
    {
      title: '账号名称',
      dataIndex: 'account_name',
      key: 'account_name',
      width: 150,
    },
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
      width: 150,
    },
    {
      title: '平台',
      dataIndex: 'platform',
      key: 'platform',
      width: 120,
      render: (v) => v === 'qidian' ? '起点中文网' : v,
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
      title: '最后登录',
      dataIndex: 'last_login_at',
      key: 'last_login_at',
      width: 180,
      render: (v) => v ? new Date(v).toLocaleString('zh-CN') : '-',
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
      width: 200,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<SafetyCertificateOutlined />}
            loading={verifying === record.id}
            onClick={() => handleVerify(record.id)}
          >
            验证
          </Button>
          <Popconfirm
            title="确定要删除该账号吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        title="平台账号管理"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={fetchAccounts}>
              刷新
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalOpen(true)}
            >
              添加账号
            </Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={accounts}
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

      {/* 创建账号弹窗 */}
      <Modal
        title="添加平台账号"
        open={createModalOpen}
        onCancel={() => {
          setCreateModalOpen(false);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        okText="添加"
        cancelText="取消"
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreate}
        >
          <Form.Item
            name="account_name"
            label="账号名称"
            rules={[{ required: true, message: '请输入账号名称' }]}
            extra="用于在系统中标识该账号"
          >
            <Input placeholder="例如：我的起点账号" />
          </Form.Item>
          <Form.Item
            name="username"
            label="登录用户名"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input placeholder="起点登录用户名" />
          </Form.Item>
          <Form.Item
            name="password"
            label="登录密码"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password placeholder="起点登录密码" />
          </Form.Item>
          <Text type="secondary" style={{ fontSize: 12 }}>
            密码将被加密存储，仅用于自动登录平台发布内容
          </Text>
        </Form>
      </Modal>
    </div>
  );
}
