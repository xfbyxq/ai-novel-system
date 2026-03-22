import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Table, Tag, Button, Modal, message, Space, Typography, Tooltip } from 'antd';
import { DeleteOutlined, EditOutlined, CheckCircleOutlined, ClockCircleOutlined } from '@ant-design/icons';
import type { Chapter } from '@/api/types';
import { getChapters, deleteChapter, batchDeleteChapters } from '@/api/chapters';
import StatusBadge from '@/components/StatusBadge';
import ChapterOutlineTaskModal, { type ChapterTask } from '@/components/ChapterOutlineTaskModal';
import { formatWordCount, formatDate } from '@/utils/format';

interface Props {
  novelId: string;
}

export default function ChaptersTab({ novelId }: Props) {
  const navigate = useNavigate();
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [deleteModalVisible, setDeleteModalVisible] = useState(false);
  const [deleteChapterInfo, setDeleteChapterInfo] = useState<{ chapterNumber: number; isBatch: boolean } | null>(null);
  const [chapterTaskModalOpen, setChapterTaskModalOpen] = useState(false);
  const [currentChapterTask, setCurrentChapterTask] = useState<ChapterTask | null>(null);
  const [pendingChapterNumber, setPendingChapterNumber] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getChapters(novelId, page, 20);
      setChapters(res.items);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  }, [novelId, page]);

  useEffect(() => { load(); }, [load]);

  const handleChapterTaskConfirm = useCallback(() => {
    setChapterTaskModalOpen(false);
    if (pendingChapterNumber !== null) {
      navigate(`/novels/${novelId}/chapters/${pendingChapterNumber}/edit`);
    }
    setCurrentChapterTask(null);
    setPendingChapterNumber(null);
  }, [novelId, pendingChapterNumber, navigate]);

  const handleChapterTaskCancel = useCallback(() => {
    setChapterTaskModalOpen(false);
    setCurrentChapterTask(null);
    setPendingChapterNumber(null);
  }, []);

  const handleDelete = (chapterNumber: number) => {
    setDeleteChapterInfo({ chapterNumber, isBatch: false });
    setDeleteModalVisible(true);
  };

  const handleBatchDelete = () => {
    if (selectedRowKeys.length === 0) return;
    setDeleteChapterInfo({ chapterNumber: 0, isBatch: true });
    setDeleteModalVisible(true);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteChapterInfo) return;
    
    setLoading(true);
    try {
      if (deleteChapterInfo.isBatch) {
        const chapterNumbers = selectedRowKeys.map(key => {
          const chapter = chapters.find(c => c.id === key);
          return chapter?.chapter_number || 0;
        }).filter(num => num > 0);
        
        await batchDeleteChapters(novelId, chapterNumbers);
        message.success('批量删除成功');
      } else {
        await deleteChapter(novelId, deleteChapterInfo.chapterNumber);
        message.success('删除成功');
      }
      
      setDeleteModalVisible(false);
      setSelectedRowKeys([]);
      await load();
    } catch (error) {
      message.error('删除失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteModalVisible(false);
    setDeleteChapterInfo(null);
  };

  const rowSelection = {
    selectedRowKeys,
    onChange: (keys: React.Key[]) => {
      setSelectedRowKeys(keys);
    },
  };

  const getOutlineStatusIcon = (chapter: Chapter) => {
    if (chapter.status === 'published') {
      return (
        <Tooltip title="已发布">
          <CheckCircleOutlined style={{ color: '#52c41a' }} />
        </Tooltip>
      );
    }
    if (chapter.status === 'reviewing') {
      return (
        <Tooltip title="审核中">
          <CheckCircleOutlined style={{ color: '#1890ff' }} />
        </Tooltip>
      );
    }
    return (
      <Tooltip title="待生成">
        <ClockCircleOutlined style={{ color: '#faad14' }} />
      </Tooltip>
    );
  };

  return (
    <>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <Typography.Text strong>章节列表</Typography.Text>
          <Tooltip title="章节大纲完成状态">
            <Space size="small">
              <CheckCircleOutlined style={{ color: '#52c41a' }} />
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>已完成</Typography.Text>
              <ClockCircleOutlined style={{ color: '#faad14' }} />
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>待生成</Typography.Text>
            </Space>
          </Tooltip>
        </Space>
        {selectedRowKeys.length > 0 && (
          <Button 
            danger 
            icon={<DeleteOutlined />} 
            onClick={handleBatchDelete}
          >
            批量删除 ({selectedRowKeys.length})
          </Button>
        )}
      </div>
      
      <Table
        dataSource={chapters}
        rowKey="id"
        loading={loading}
        rowSelection={rowSelection}
        pagination={{ current: page, pageSize: 20, total, onChange: setPage }}
        columns={[
          { 
            title: '大纲状态', 
            dataIndex: 'status', 
            width: 90,
            render: (_: any, record: Chapter) => getOutlineStatusIcon(record),
          },
          { title: '章节', dataIndex: 'chapter_number', width: 70, render: (v: number) => `第 ${v} 章` },
          { title: '卷', dataIndex: 'volume_number', width: 60 },
          {
            title: '标题', dataIndex: 'title', render: (v: string, r: Chapter) => (
              <a onClick={() => navigate(`/novels/${novelId}/chapters/${r.chapter_number}`)}>{v || '(未命名)'}</a>
            ),
          },
          { title: '字数', dataIndex: 'word_count', width: 80, render: formatWordCount },
          {
            title: '质量', dataIndex: 'quality_score', width: 80,
            render: (v: number | null) => v != null ? <Tag color={v >= 8 ? 'green' : v >= 6 ? 'orange' : 'red'}>{v}</Tag> : '-',
          },
          { title: '状态', dataIndex: 'status', width: 90, render: (v: string) => <StatusBadge type="chapter" status={v} /> },
          { title: '创建时间', dataIndex: 'created_at', width: 160, render: formatDate },
          {
            title: '操作',
            width: 150,
            render: (_: any, record: Chapter) => (
              <Space size="small">
                <Button 
                  type="link" 
                  size="small" 
                  icon={<EditOutlined />}
                  onClick={() => navigate(`/novels/${novelId}/chapters/${record.chapter_number}/edit`)}
                >
                  编辑
                </Button>
                <Button 
                  danger 
                  icon={<DeleteOutlined />} 
                  size="small" 
                  onClick={() => handleDelete(record.chapter_number)}
                />
              </Space>
            ),
          },
        ]}
      />
      
      <Modal
        title={deleteChapterInfo?.isBatch ? '批量删除章节' : '删除章节'}
        open={deleteModalVisible}
        onOk={handleDeleteConfirm}
        onCancel={handleDeleteCancel}
        okText="确认删除"
        cancelText="取消"
        okType="danger"
      >
        <p>
          {deleteChapterInfo?.isBatch 
            ? `确定要删除选中的 ${selectedRowKeys.length} 个章节吗？`
            : `确定要删除第 ${deleteChapterInfo?.chapterNumber} 章吗？`}
        </p>
        <p style={{ color: '#ff4d4f', marginTop: 8 }}>删除后无法恢复，请谨慎操作。</p>
      </Modal>

      <ChapterOutlineTaskModal
        open={chapterTaskModalOpen}
        task={currentChapterTask}
        onConfirm={handleChapterTaskConfirm}
        onCancel={handleChapterTaskCancel}
      />
    </>
  );
}
