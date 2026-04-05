import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Spin, Typography, Breadcrumb, Card, Space, Button, Tag, Divider,
  Modal, Form, Input, Select, message,
} from 'antd';
import { HomeOutlined, LeftOutlined, RightOutlined, EditOutlined, RobotOutlined } from '@ant-design/icons';
import type { Chapter, Novel } from '@/api/types';
import { getChapter, getChapters, updateChapter } from '@/api/chapters';
import { getNovel } from '@/api/novels';
import { formatWordCount, formatDate } from '@/utils/format';
import AIChatDrawer from '@/components/AIChatDrawer';

export default function ChapterReader() {
  const { id: novelId, number } = useParams<{ id: string; number: string }>();
  const navigate = useNavigate();
  const [chapter, setChapter] = useState<Chapter | null>(null);
  const [novel, setNovel] = useState<Novel | null>(null); // 小说信息
  const [totalChapters, setTotalChapters] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [editOpen, setEditOpen] = useState(false);
  const [editLoading, setEditLoading] = useState(false);
  const [form] = Form.useForm();
  const [aiChatOpen, setAiChatOpen] = useState(false); // AI助手抽屉状态

  const fetchChapter = useCallback(async (nid: string, num: string) => {
    setLoading(true);
    try {
      const [data, listRes, novelData] = await Promise.all([
        getChapter(nid, parseInt(num)),
        getChapters(nid, 1, 1),
        getNovel(nid), // 获取小说信息
      ]);
      setChapter(data);
      setTotalChapters(listRes.total);
      setNovel(novelData); // 存储小说信息
    } catch {
      /* handled by interceptor */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!novelId || !number) return;
    void fetchChapter(novelId, number);
  }, [novelId, number, fetchChapter]);

  const handleEdit = () => {
    if (!chapter) return;
    form.setFieldsValue({
      title: chapter.title || '',
      content: chapter.content || '',
      status: chapter.status,
    });
    setEditOpen(true);
  };

  const handleSave = async () => {
    if (!novelId || !number) return;
    setEditLoading(true);
    try {
      const values = await form.validateFields();
      await updateChapter(novelId, parseInt(number), values);
      message.success('章节已保存');
      setEditOpen(false);
      void fetchChapter(novelId, number);
    } finally {
      setEditLoading(false);
    }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!chapter || !novelId) return <Typography.Text>章节不存在</Typography.Text>;

  const chapterNum = parseInt(number || '1');

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          { title: <><HomeOutlined /> 首页</>, onClick: () => navigate('/') },
          { title: '小说详情', onClick: () => navigate(`/novels/${novelId}`) },
          { title: `第 ${chapter.chapter_number} 章` },
        ]}
      />

      <Card>
        <Space style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
          <Typography.Title level={3} style={{ margin: 0 }}>
            {chapter.title || `第 ${chapter.chapter_number} 章`}
          </Typography.Title>
          <Space>
            <Button 
              type="primary" 
              icon={<RobotOutlined />} 
              onClick={() => setAiChatOpen(true)}
            >
              AI 助手
            </Button>
            <Button icon={<EditOutlined />} onClick={handleEdit}>编辑</Button>
          </Space>
        </Space>

        <Space style={{ display: 'flex', justifyContent: 'center', marginBottom: 24 }}>
          <Tag>第 {chapter.volume_number} 卷</Tag>
          <Tag>{formatWordCount(chapter.word_count)} 字</Tag>
          {chapter.quality_score != null && (
            <Tag color={chapter.quality_score >= 8 ? 'green' : 'orange'}>
              质量: {chapter.quality_score}
            </Tag>
          )}
          <Typography.Text type="secondary">{formatDate(chapter.created_at)}</Typography.Text>
        </Space>

        <Divider />

        <div style={{ lineHeight: 2, fontSize: 16, textIndent: '2em' }}>
          {chapter.content ? (
            chapter.content.split('\n').map((p, i) => (
              p.trim() ? <p key={i}>{p}</p> : <br key={i} />
            ))
          ) : (
            <Typography.Text type="secondary">暂无内容</Typography.Text>
          )}
        </div>

        <Divider />

        <Space style={{ display: 'flex', justifyContent: 'space-between' }}>
          <Button
            icon={<LeftOutlined />}
            disabled={chapterNum <= 1}
            onClick={() => navigate(`/novels/${novelId}/chapters/${chapterNum - 1}`)}
          >
            上一章
          </Button>
          <Button
            disabled={chapterNum >= totalChapters}
            onClick={() => navigate(`/novels/${novelId}/chapters/${chapterNum + 1}`)}
          >
            下一章 <RightOutlined />
          </Button>
        </Space>
      </Card>

      <Modal
        title="编辑章节"
        open={editOpen}
        onOk={handleSave}
        confirmLoading={editLoading}
        onCancel={() => setEditOpen(false)}
        okText="保存"
        width={720}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="标题">
            <Input placeholder="章节标题" />
          </Form.Item>
          <Form.Item name="content" label="内容">
            <Input.TextArea rows={20} placeholder="章节正文" />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select options={[
              { value: 'draft', label: '草稿' },
              { value: 'reviewing', label: '审核中' },
              { value: 'published', label: '已发布' },
            ]} />
          </Form.Item>
        </Form>
      </Modal>

      {/* AI助手抽屉 */}
      <AIChatDrawer
        open={aiChatOpen}
        onClose={() => setAiChatOpen(false)}
        scene="chapter_assistant"
        novelId={novelId ? novelId : undefined}
        novelTitle={novel?.title ?? undefined}
        chapterNumber={chapter?.chapter_number}
      />
    </div>
  );
}
