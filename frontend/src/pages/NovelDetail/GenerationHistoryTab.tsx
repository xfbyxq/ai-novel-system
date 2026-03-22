import { useCallback, useEffect, useRef } from 'react';
import { Table, Button, Space, Progress, Typography } from 'antd';
import { ReloadOutlined, StopOutlined } from '@ant-design/icons';
import type { GenerationTask } from '@/api/types';
import { useGenerationStore } from '@/stores/useGenerationStore';
import { cancelGenerationTask } from '@/api/generation';
import { usePolling } from '@/hooks/usePolling';
import StatusBadge from '@/components/StatusBadge';
import { formatDate, formatCost } from '@/utils/format';

interface Props {
  novelId: string;
  onNovelRefresh: () => void;
}

export default function GenerationHistoryTab({ novelId, onNovelRefresh }: Props) {
  const { tasks, loading, fetchTasks, refreshTask } = useGenerationStore();
  const notifiedTaskIds = useRef(new Set<string>());

  useEffect(() => {
    void fetchTasks(novelId);
    return () => {
      notifiedTaskIds.current.clear();
    };
  }, [fetchTasks, novelId]);

  const pollCallback = useCallback(async () => {
    const prevTasks = useGenerationStore.getState().tasks;
    await fetchTasks(novelId);
    const currentTasks = useGenerationStore.getState().tasks;
    
    for (const task of currentTasks) {
      const prevTask = prevTasks.find(t => t.id === task.id);
      const isNewlyCompleted = task.status === 'completed' && prevTask?.status === 'running';
      const isNewlyFailed = task.status === 'failed' && prevTask?.status === 'running';
      
      if (isNewlyCompleted && !notifiedTaskIds.current.has(task.id)) {
        notifiedTaskIds.current.add(task.id);
        onNovelRefresh();
      } else if (isNewlyFailed && !notifiedTaskIds.current.has(task.id)) {
        notifiedTaskIds.current.add(task.id);
      }
    }
  }, [novelId, fetchTasks, onNovelRefresh]);

  const hasRunning = tasks.some((t) => t.status === 'running' || t.status === 'pending');
  usePolling(pollCallback, 3000, hasRunning);

  const handleCancel = async (taskId: string) => {
    await cancelGenerationTask(taskId);
    await refreshTask(taskId);
  };

  return (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <Button icon={<ReloadOutlined />} onClick={() => fetchTasks(novelId)} loading={loading}>
          刷新
        </Button>
        {hasRunning && <StatusBadge type="task" status="running" />}
      </Space>
      <Table
        dataSource={tasks}
        rowKey="id"
        loading={loading}
        pagination={false}
        columns={[
          {
            title: '类型', dataIndex: 'task_type', width: 100,
            render: (v: string) => {
              if (v === 'planning') return '企划';
              if (v === 'writing') return '单章写作';
              if (v === 'batch_writing') return '批量写作';
              if (v === 'outline_refinement') return '大纲完善';
              return v;
            },
          },
          { title: '状态', dataIndex: 'status', width: 100, render: (v: string) => <StatusBadge type="task" status={v} /> },
          {
            title: '进度', width: 150,
            render: (_: unknown, r: GenerationTask) => {
              if (r.task_type === 'batch_writing' && r.output_data) {
                const { completed_chapters = 0, total_chapters = 0 } = r.output_data as {
                  completed_chapters?: number;
                  total_chapters?: number;
                };
                if (total_chapters > 0) {
                  const percent = Math.round((completed_chapters / total_chapters) * 100);
                  return (
                    <div>
                      <Progress percent={percent} size="small" />
                      <Typography.Text type="secondary" style={{ fontSize: '12px' }}>
                        {completed_chapters}/{total_chapters} 章
                      </Typography.Text>
                    </div>
                  );
                }
              }
              return '-';
            },
          },
          { title: 'Tokens', dataIndex: 'token_usage', width: 80 },
          { title: '成本', dataIndex: 'cost', width: 100, render: formatCost },
          { title: '开始', dataIndex: 'started_at', width: 150, render: formatDate },
          { title: '完成', dataIndex: 'completed_at', width: 150, render: formatDate },
          {
            title: '操作', width: 80,
            render: (_: unknown, r: GenerationTask) => (
              (r.status === 'running' || r.status === 'pending') ? (
                <Button size="small" danger icon={<StopOutlined />} onClick={() => handleCancel(r.id)}>
                  取消
                </Button>
              ) : null
            ),
          },
        ]}
      />
    </div>
  );
}
