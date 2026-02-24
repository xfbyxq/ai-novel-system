import { useState, useEffect } from 'react';
import { Card, Row, Col, Typography, Spin, Alert, Table, Modal, Tag, Space, Descriptions, Progress, Statistic, Button } from 'antd';
import {
  ApiOutlined,
  HistoryOutlined,
} from '@ant-design/icons';
import apiClient from '@/api/client';
import dayjs from 'dayjs';

const { Title, Text } = Typography;

interface AgentStatus {
  agent_id: string;
  agent_name: string;
  status: 'idle' | 'busy' | 'error' | 'starting' | 'stopping';
  last_activity: string;
  current_task?: string;
  error_message?: string;
}

interface SystemMetrics {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  uptime: number;
  total_tasks: number;
  successful_tasks: number;
  failed_tasks: number;
}

interface TaskHistory {
  task_id: string;
  agent_name: string;
  task_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  start_time: string;
  end_time?: string;
  duration?: number;
  error_message?: string;
}

const SystemMonitoring = () => {
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [metrics, setMetrics] = useState<SystemMetrics>({
    cpu_usage: 0,
    memory_usage: 0,
    disk_usage: 0,
    uptime: 0,
    total_tasks: 0,
    successful_tasks: 0,
    failed_tasks: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [historyModalVisible, setHistoryModalVisible] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<string>('');
  const [taskHistory, setTaskHistory] = useState<TaskHistory[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const fetchSystemStatus = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.get('/monitoring/system-status');
      const data = response.data.data || {};
      
      // 获取Agent状态数据
      setAgents(data.agents || []);
      
      // 适配后端返回的metrics数据结构
      setMetrics({
        cpu_usage: data.system?.cpu_percent || 0,
        memory_usage: data.system?.memory?.percent || 0,
        disk_usage: data.system?.disk?.percent || 0,
        uptime: data.system?.uptime_seconds || 0,
        total_tasks: (data.tasks?.generation?.total || 0) + 
                   (data.tasks?.publish?.total || 0) + 
                   (data.tasks?.crawler?.total || 0),
        successful_tasks: (data.tasks?.generation?.completed || 0) + 
                        (data.tasks?.publish?.completed || 0),
        failed_tasks: (data.tasks?.generation?.failed || 0) + 
                     (data.tasks?.publish?.failed || 0),
      });
    } catch (err) {
      setError('获取系统状态失败');
      console.error('Error fetching system status:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchTaskHistory = async (agentId: string) => {
    try {
      setHistoryLoading(true);
      const response = await apiClient.get(`/monitoring/agent-history/${agentId}`);
      setTaskHistory(response.data || []);
    } catch (err) {
      console.error('Error fetching task history:', err);
      setTaskHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    fetchSystemStatus();
    const interval = setInterval(fetchSystemStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const showHistoryModal = (agentId: string) => {
    setSelectedAgent(agentId);
    fetchTaskHistory(agentId);
    setHistoryModalVisible(true);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'idle':
        return 'green';
      case 'busy':
        return 'blue';
      case 'error':
        return 'red';
      case 'starting':
        return 'orange';
      case 'stopping':
        return 'yellow';
      default:
        return 'default';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'idle':
        return '空闲';
      case 'busy':
        return '忙碌';
      case 'error':
        return '错误';
      case 'starting':
        return '启动中';
      case 'stopping':
        return '停止中';
      default:
        return status;
    }
  };

  const taskHistoryColumns = [
    {
      title: '任务ID',
      dataIndex: 'task_id',
      key: 'task_id',
      ellipsis: true,
    },
    {
      title: '任务类型',
      dataIndex: 'task_type',
      key: 'task_type',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        let color = 'default';
        switch (status) {
          case 'pending':
            color = 'blue';
            break;
          case 'running':
            color = 'orange';
            break;
          case 'completed':
            color = 'green';
            break;
          case 'failed':
            color = 'red';
            break;
        }
        return <Tag color={color}>{status}</Tag>;
      },
    },
    {
      title: '开始时间',
      dataIndex: 'start_time',
      key: 'start_time',
      render: (time: string) => dayjs(time).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '结束时间',
      dataIndex: 'end_time',
      key: 'end_time',
      render: (time?: string) => time ? dayjs(time).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
    {
      title: '耗时(秒)',
      dataIndex: 'duration',
      key: 'duration',
      render: (duration?: number) => duration ? duration.toFixed(2) : '-',
    },
  ];

  const successRate = metrics.total_tasks > 0 
    ? (metrics.successful_tasks / metrics.total_tasks) * 100 
    : 0;

  return (
    <div style={{ padding: 24 }}>
      <Title level={2}>系统监控</Title>
      
      {error && (
        <Alert
          title="错误"
          description={error}
          type="error"
          showIcon
          style={{ marginBottom: 24 }}
        />
      )}

      <Spin spinning={loading} description="加载系统状态...">
        {/* 系统健康度卡片 */}
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col xs={24} sm={12} md={8}>
            <Card title="CPU 使用率" variant="borderless">
              <Statistic
                value={metrics.cpu_usage}
                suffix="%"
                precision={1}
                styles={{
                  content: {
                    color: metrics.cpu_usage > 80 ? '#ff4d4f' : '#52c41a',
                  },
                }}
              />
              <Progress
                percent={metrics.cpu_usage}
                status={metrics.cpu_usage > 80 ? 'exception' : metrics.cpu_usage > 60 ? 'active' : 'normal'}
                style={{ marginTop: 16 }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={8}>
            <Card title="内存使用率" variant="borderless">
              <Statistic
                value={metrics.memory_usage}
                suffix="%"
                precision={1}
                styles={{
                  content: {
                    color: metrics.memory_usage > 80 ? '#ff4d4f' : '#52c41a',
                  },
                }}
              />
              <Progress
                percent={metrics.memory_usage}
                status={metrics.memory_usage > 80 ? 'exception' : metrics.memory_usage > 60 ? 'active' : 'normal'}
                style={{ marginTop: 16 }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={8}>
            <Card title="磁盘使用率" variant="borderless">
              <Statistic
                value={metrics.disk_usage}
                suffix="%"
                precision={1}
                styles={{
                  content: {
                    color: metrics.disk_usage > 80 ? '#ff4d4f' : '#52c41a',
                  },
                }}
              />
              <Progress
                percent={metrics.disk_usage}
                status={metrics.disk_usage > 80 ? 'exception' : metrics.disk_usage > 60 ? 'active' : 'normal'}
                style={{ marginTop: 16 }}
              />
            </Card>
          </Col>
        </Row>

        {/* 任务统计卡片 */}
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col xs={24} sm={12} md={8}>
            <Card title="任务成功率" variant="borderless">
              <Statistic
                value={successRate}
                suffix="%"
                precision={1}
                styles={{
                  content: {
                    color: successRate < 80 ? '#ff4d4f' : '#52c41a',
                  },
                }}
              />
              <Progress
                percent={successRate}
                status={successRate < 60 ? 'exception' : successRate < 80 ? 'active' : 'normal'}
                style={{ marginTop: 16 }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={8}>
            <Card title="系统运行时间" variant="borderless">
              <Statistic
                value={Math.floor(metrics.uptime / 3600)}
                suffix="小时"
                precision={0}
              />
              <Text style={{ display: 'block', marginTop: 8, color: '#666' }}>
                总任务数: {metrics.total_tasks}
              </Text>
            </Card>
          </Col>
          <Col xs={24} sm={12} md={8}>
            <Card title="任务状态" variant="borderless">
              <Space orientation="vertical" style={{ width: '100%' }}>
                <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                  <Text>成功: {metrics.successful_tasks}</Text>
                  <Text>失败: {metrics.failed_tasks}</Text>
                </Space>
                <Progress
                  percent={(metrics.successful_tasks / (metrics.total_tasks || 1)) * 100}
                  format={() => `${metrics.successful_tasks}/${metrics.total_tasks}`}
                />
              </Space>
            </Card>
          </Col>
        </Row>

        {/* Agent 状态卡片 */}
        <Title level={3} style={{ marginBottom: 16 }}>Agent 状态</Title>
        <Row gutter={[16, 16]}>
          {agents.map((agent) => (
            <Col key={agent.agent_id} xs={24} sm={12} md={8} lg={6}>
              <Card
                title={
                  <Space>
                    <ApiOutlined />
                    <Text strong>{agent.agent_name}</Text>
                  </Space>
                }
                variant="borderless"
                extra={
                  <Tag color={getStatusColor(agent.status)}>
                    {getStatusText(agent.status)}
                  </Tag>
                }
                actions={[
                  <Button 
                    key="history" 
                    icon={<HistoryOutlined />} 
                    onClick={() => showHistoryModal(agent.agent_id)}
                  >
                    查看历史
                  </Button>
                ]}
              >
                <Descriptions size="small" column={1}>
                  <Descriptions.Item label="最后活动">
                    {dayjs(agent.last_activity).format('YYYY-MM-DD HH:mm:ss')}
                  </Descriptions.Item>
                  {agent.current_task && (
                    <Descriptions.Item label="当前任务">
                      <Text ellipsis={{ tooltip: agent.current_task }}>
                        {agent.current_task}
                      </Text>
                    </Descriptions.Item>
                  )}
                  {agent.error_message && (
                    <Descriptions.Item label="错误信息" style={{ color: '#ff4d4f' }}>
                      <Text ellipsis={{ tooltip: agent.error_message }}>
                        {agent.error_message}
                      </Text>
                    </Descriptions.Item>
                  )}
                </Descriptions>
              </Card>
            </Col>
          ))}
        </Row>
      </Spin>

      {/* 历史任务记录模态框 */}
      <Modal
        title={`${selectedAgent} - 历史任务记录`}
        open={historyModalVisible}
        onCancel={() => setHistoryModalVisible(false)}
        footer={null}
        width={800}
      >
        <Spin spinning={historyLoading} description="加载历史任务...">
          <Table
            columns={taskHistoryColumns}
            dataSource={taskHistory}
            rowKey="task_id"
            pagination={{ pageSize: 10 }}
            scroll={{ y: 400 }}
            locale={{ emptyText: '暂无历史任务记录' }}
          />
        </Spin>
      </Modal>
    </div>
  );
};

export default SystemMonitoring;