import { useEffect, useRef, useState } from 'react';
import {
  Drawer, Input, Button, Typography, Spin, Space, Divider, List, Modal, Popconfirm, message, Select, Form, Card,
} from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, ReloadOutlined, HistoryOutlined, DeleteOutlined, CheckCircleOutlined, BookOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { createChatSession, getWebSocketUrl, sendChatMessage, listSessions, deleteSession as deleteSessionApi } from '@/api/aiChat';
import { updateWorldSetting, updatePlotOutline } from '@/api/novels';

const { TextArea } = Input;
const { Option } = Select;

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  scene: 'novel_creation' | 'crawler_task' | 'novel_revision' | 'novel_analysis';
  novelId?: string;
  novelTitle?: string;
}

export default function AIChatDrawer({ open, onClose, scene, novelId, novelTitle }: Props) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sessions, setSessions] = useState<any[]>([]);
  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [chapterRange, setChapterRange] = useState({ start: 1, end: 10 });

  const [streaming, setStreaming] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const initSession = async () => {
    try {
      const context = novelId ? { 
        novel_id: novelId, 
        chapter_start: chapterRange.start, 
        chapter_end: chapterRange.end 
      } : undefined;
      const response = await createChatSession({ scene, context });
      setSessionId(response.session_id);
      setMessages([{ role: 'assistant', content: response.welcome_message }]);
    } catch (error) {
      console.error('创建会话失败:', error);
      message.error('创建会话失败，请重试');
    }
  };

  useEffect(() => {
    if (open && !sessionId) {
      initSession();
    }
  }, [open, sessionId, scene, novelId]);

  useEffect(() => {
    if (!sessionId || !open) return;

    const wsUrl = getWebSocketUrl(sessionId);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket 连接已建立');
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.error) {
        console.error('WebSocket 错误:', data.error);
        setStreaming(false);
        return;
      }

      if (!data.done) {
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.role === 'assistant') {
            return [
              ...prev.slice(0, -1),
              { ...last, content: last.content + data.chunk },
            ];
          }
          return [...prev, { role: 'assistant', content: data.chunk }];
        });
      } else {
        setStreaming(false);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket 错误:', error);
      setStreaming(false);
    };

    ws.onclose = () => {
      console.log('WebSocket 连接已关闭');
      setStreaming(false);
    };

    return () => {
      ws.close();
    };
  }, [sessionId, open]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || streaming || !sessionId) return;

    const userMessage = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setStreaming(true);

    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ message: userMessage }));
    } else {
      try {
        const response = await sendChatMessage(sessionId, { message: userMessage });
        setMessages((prev) => [...prev, { role: 'assistant', content: response.message }]);
        setStreaming(false);
      } catch (error) {
        console.error('发送消息失败:', error);
        setStreaming(false);
      }
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleRestart = () => {
    setSessionId(null);
    setMessages([]);
    initSession();
  };

  const loadSessions = async () => {
    try {
      setLoadingSessions(true);
      const response = await listSessions(scene);
      setSessions(response.sessions);
    } catch (error) {
      console.error('加载会话失败:', error);
    } finally {
      setLoadingSessions(false);
    }
  };

  const handleLoadSession = (session: any) => {
    setSessionId(session.session_id);
    // 这里可以添加加载历史消息的逻辑
    setHistoryModalOpen(false);
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await deleteSessionApi(sessionId);
      // 重新加载会话列表
      await loadSessions();
    } catch (error) {
      console.error('删除会话失败:', error);
    }
  };

  const parseRevisionSuggestion = (content: string) => {
    /** 解析AI的修订建议 */
    // 简单的解析逻辑，实际应用中可能需要更复杂的NLP处理
    const suggestions = [];
    
    // 检测世界观修订建议
    if (content.includes('世界观') || content.includes('世界设定')) {
      suggestions.push({
        type: 'world_setting',
        content: content,
        description: '世界观修订建议'
      });
    }
    
    // 检测角色修订建议
    if (content.includes('角色') || content.includes('人物')) {
      suggestions.push({
        type: 'character',
        content: content,
        description: '角色修订建议'
      });
    }
    
    // 检测大纲修订建议
    if (content.includes('大纲') || content.includes('剧情')) {
      suggestions.push({
        type: 'outline',
        content: content,
        description: '大纲修订建议'
      });
    }
    
    // 检测章节修订建议
    if (content.includes('章节') || content.includes('内容')) {
      suggestions.push({
        type: 'chapter',
        content: content,
        description: '章节修订建议'
      });
    }
    
    return suggestions;
  };

  const applySuggestion = async (suggestion: any) => {
    /** 应用修订建议 */
    if (!novelId) {
      message.error('缺少小说ID，无法应用建议');
      return;
    }
    
    try {
      message.loading('正在应用建议...');
      
      switch (suggestion.type) {
        case 'world_setting':
          // 提取世界观内容
          // 这里需要更复杂的解析逻辑来提取具体的修订内容
          await updateWorldSetting(novelId, { content: suggestion.content });
          break;
        case 'outline':
          // 提取大纲内容
          await updatePlotOutline(novelId, { content: suggestion.content });
          break;
        case 'character':
          // 提取角色内容
          // 这里需要更复杂的解析逻辑来确定具体要修改哪个角色
          message.info('角色修订需要手动选择具体角色');
          break;
        case 'chapter':
          // 提取章节内容
          // 这里需要更复杂的解析逻辑来确定具体要修改哪章
          message.info('章节修订需要手动选择具体章节');
          break;
        default:
          message.error('未知的修订类型');
          return;
      }
      
      message.success('建议应用成功！');
    } catch (error) {
      console.error('应用建议失败:', error);
      message.error('应用建议失败，请重试');
    }
  };

  const getSceneTitle = () => {
    switch (scene) {
      case 'novel_creation':
        return '小说创作助手';
      case 'novel_revision':
        return '小说修订助手';
      case 'novel_analysis':
        return '小说分析助手';
      case 'crawler_task':
        return '爬虫策略助手';
      default:
        return 'AI助手';
    }
  };

  const title = getSceneTitle();

  return (
    <>
      <Drawer
        title={
          <Space direction="vertical" style={{ width: '100%' }}>
            <Space>
              <RobotOutlined />
              <span style={{ fontSize: '16px', fontWeight: 'bold' }}>{title}</span>
              {novelTitle && (
                <Card size="small" style={{ marginLeft: 'auto', background: '#f0f9ff' }}>
                  <Space>
                    <BookOutlined />
                    <Typography.Text ellipsis style={{ maxWidth: 200 }}>{novelTitle}</Typography.Text>
                  </Space>
                </Card>
              )}
            </Space>
            {(scene === 'novel_revision' || scene === 'novel_analysis') && novelId && (
              <Space style={{ marginTop: 8, justifyContent: 'space-between', width: '100%' }}>
                <Typography.Text type="secondary">章节范围</Typography.Text>
                <Space>
                  <Input
                    type="number"
                    min={1}
                    value={chapterRange.start}
                    onChange={(e) => setChapterRange({ ...chapterRange, start: parseInt(e.target.value) || 1 })}
                    style={{ width: 80 }}
                  />
                  <span>至</span>
                  <Input
                    type="number"
                    min={chapterRange.start}
                    value={chapterRange.end}
                    onChange={(e) => setChapterRange({ ...chapterRange, end: parseInt(e.target.value) || chapterRange.start })}
                    style={{ width: 80 }}
                  />
                  <Button size="small" onClick={handleRestart}>
                    应用
                  </Button>
                </Space>
              </Space>
            )}
            <Space style={{ marginTop: 8 }}>
              <Button size="small" icon={<HistoryOutlined />} onClick={() => {
                loadSessions();
                setHistoryModalOpen(true);
              }} />
              <Button size="small" icon={<ReloadOutlined />} onClick={handleRestart} />
            </Space>
          </Space>
        }
        placement="right"
        size="large"
        style={{ width: 560 }}
        open={open}
        onClose={onClose}
      >
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div style={{ flex: 1, overflowY: 'auto', padding: '16px 0' }}>
            {messages.map((msg, index) => (
              <div key={index} style={{ marginBottom: 16 }}>
                <Space align="start">
                  {msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                  <div
                    style={{
                      background: msg.role === 'user' ? '#e6f7ff' : '#f5f5f5',
                      padding: '8px 12px',
                      borderRadius: 8,
                      maxWidth: '85%',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    <Typography.Text>{msg.content}</Typography.Text>
                    {msg.role === 'assistant' && scene === 'novel_revision' && (
                      <div style={{ marginTop: 8, display: 'flex', justifyContent: 'flex-end' }}>
                        <Button 
                          size="small" 
                          type="primary" 
                          icon={<CheckCircleOutlined />}
                          onClick={() => {
                            const suggestions = parseRevisionSuggestion(msg.content);
                            if (suggestions.length > 0) {
                              // 简单处理，只应用第一个建议
                              applySuggestion(suggestions[0]);
                            } else {
                              message.info('未检测到可应用的修订建议');
                            }
                          }}
                        >
                          应用建议
                        </Button>
                      </div>
                    )}
                  </div>
                </Space>
              </div>
            ))}
            {streaming && (
              <div style={{ marginBottom: 16 }}>
                <Space align="start">
                  <RobotOutlined />
                  <div style={{ background: '#f5f5f5', padding: '8px 12px', borderRadius: 8 }}>
                    <Spin size="small" />
                    <Typography.Text type="secondary" style={{ marginLeft: 8 }}>AI 正在思考...</Typography.Text>
                  </div>
                </Space>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <Divider style={{ margin: '12px 0' }} />

          <div>
            <TextArea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="输入你的问题或需求..."
              autoSize={{ minRows: 2, maxRows: 6 }}
              disabled={streaming}
            />
            <div style={{ marginTop: 8, textAlign: 'right' }}>
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                loading={streaming}
                disabled={!input.trim()}
              >
                发送
              </Button>
            </div>
          </div>
        </div>
      </Drawer>

      <Modal
        title="历史会话"
        open={historyModalOpen}
        onCancel={() => setHistoryModalOpen(false)}
        footer={[
          <Button key="close" onClick={() => setHistoryModalOpen(false)}>
            关闭
          </Button>,
        ]}
        width={600}
      >
        <Spin spinning={loadingSessions}>
          <List
            itemLayout="horizontal"
            dataSource={sessions}
            renderItem={(session) => (
              <List.Item
                actions={[
                  <Button 
                    key="load" 
                    type="primary" 
                    size="small"
                    onClick={() => handleLoadSession(session)}
                  >
                    加载
                  </Button>,
                  <Popconfirm
                    title="确定要删除这个会话吗？"
                    onConfirm={() => handleDeleteSession(session.session_id)}
                    okText="确定"
                    cancelText="取消"
                  >
                    <Button 
                      key="delete" 
                      danger 
                      size="small"
                      icon={<DeleteOutlined />}
                    >
                      删除
                    </Button>
                  </Popconfirm>
                ]}
              >
                <List.Item.Meta
                  title={
                    <div>
                      <Typography.Text strong>{session.scene === 'novel_creation' ? '小说创作' : session.scene === 'novel_revision' ? '小说修订' : '爬虫策略'}</Typography.Text>
                      <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
                        {new Date(session.created_at).toLocaleString()}
                      </Typography.Text>
                    </div>
                  }
                  description={
                    <div>
                      {session.context?.novel_id && (
                        <Typography.Text type="secondary">小说ID: {session.context.novel_id}</Typography.Text>
                      )}
                    </div>
                  }
                />
              </List.Item>
            )}
          />
          {!loadingSessions && sessions.length === 0 && (
            <Typography.Text type="secondary" style={{ display: 'block', textAlign: 'center', marginTop: 20 }}>
              暂无历史会话
            </Typography.Text>
          )}
        </Spin>
      </Modal>
    </>
  );
}
