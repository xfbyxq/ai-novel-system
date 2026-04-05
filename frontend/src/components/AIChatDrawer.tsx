import { useEffect, useRef, useState } from 'react';
import { 
  Drawer, Input, Button, Typography, Spin, Space, Divider, List, Modal, Popconfirm, message, Card, Tag, Radio, Tooltip,
} from 'antd';
import { EditOutlined, SendOutlined, RobotOutlined, UserOutlined, ReloadOutlined, HistoryOutlined, DeleteOutlined, BookOutlined } from '@ant-design/icons';
import { 
  createChatSession, 
  getWebSocketUrl, 
  sendChatMessage, 
  listSessions, 
  getSession,
  deleteSession as deleteSessionApi,
  extractSuggestions,
  applySuggestion,
  applySuggestions,
  getNovelCharactersForRevision,
  getNovelChaptersForRevision,
  type RevisionSuggestion,
  type CharacterListItem,
  type ChapterListItem,
} from '@/api/aiChat';

const { TextArea } = Input;

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

interface SessionItem {
  session_id: string;
  scene: string;
  novel_id?: string | null;
  title?: string | null;
  context?: {
    novel_id?: string;
  };
  created_at: string;
}

export default function AIChatDrawer({ open, onClose, scene, novelId, novelTitle }: Props) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(false);


  const [streaming, setStreaming] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 新增：建议相关状态
  const [extractingSuggestions, setExtractingSuggestions] = useState(false);
  const [suggestions, setSuggestions] = useState<RevisionSuggestion[]>([]);
  const [suggestionsModalOpen, setSuggestionsModalOpen] = useState(false);
  const [applyingSuggestions, setApplyingSuggestions] = useState(false);
  const [selectedSuggestions, setSelectedSuggestions] = useState<number[]>([]);
  
  // 角色和章节选择相关状态
  const [characterSelectModalOpen, setCharacterSelectModalOpen] = useState(false);
  const [chapterSelectModalOpen, setChapterSelectModalOpen] = useState(false);
  const [characters, setCharacters] = useState<CharacterListItem[]>([]);
  const [chapters, setChapters] = useState<ChapterListItem[]>([]);
  const [loadingCharacters, setLoadingCharacters] = useState(false);
  const [loadingChapters, setLoadingChapters] = useState(false);
  const [pendingSuggestion, setPendingSuggestion] = useState<RevisionSuggestion | null>(null);
  const [selectedTargetId, setSelectedTargetId] = useState<string | null>(null);
  


  const initSession = async () => {
    try {
      const context = novelId ? { novel_id: novelId } : undefined;
      const response = await createChatSession({ scene, context });
      setSessionId(response.session_id);
      setMessages([{ role: 'assistant', content: response.welcome_message }]);
    } catch (error) {
      console.error('创建会话失败:', error);
      message.error('创建会话失败，请重试');
    }
  };

  // 新建会话
  const handleNewSession = () => {
    setSessionId(null);
    setMessages([]);
    initSession();
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

  const loadSessions = async () => {
    try {
      setLoadingSessions(true);
      // 按场景和小说ID过滤历史会话
      const response = await listSessions(scene, novelId);
      setSessions(response.sessions);
    } catch (error) {
      console.error('加载会话失败:', error);
    } finally {
      setLoadingSessions(false);
    }
  };

  const handleLoadSession = async (session: SessionItem) => {
    try {
      const sessionDetail = await getSession(session.session_id);
      setSessionId(session.session_id);
      setMessages(sessionDetail.messages.map(msg => ({
        role: msg.role as 'user' | 'assistant',
        content: msg.content
      })));
      setHistoryModalOpen(false);
    } catch (error) {
      console.error('加载会话详情失败:', error);
      message.error('加载会话失败，请重试');
    }
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

  // 新增：从后端提取结构化建议
  const handleExtractSuggestions = async (content: string) => {
    if (!novelId) {
      message.error('缺少小说ID');
      return;
    }
    
    setExtractingSuggestions(true);
    
    try {
      const response = await extractSuggestions({
        novel_id: novelId,
        ai_response: content,
        revision_type: 'general'
      });
      
      if (response.suggestions && response.suggestions.length > 0) {
        setSuggestions(response.suggestions);
        setSelectedSuggestions(response.suggestions.map((_, idx) => idx));
        setSuggestionsModalOpen(true);
      } else {
        message.info('未检测到可提取的具体修订建议');
      }
    } catch (error) {
      console.error('提取建议失败:', error);
      message.error('提取建议失败，请重试');
    } finally {
      setExtractingSuggestions(false);
    }
  };

  // 加载角色列表
  const loadCharacters = async () => {
    if (!novelId) return;
    
    setLoadingCharacters(true);
    try {
      const response = await getNovelCharactersForRevision(novelId);
      setCharacters(response.characters);
    } catch (error) {
      console.error('加载角色列表失败:', error);
      message.error('加载角色列表失败');
    } finally {
      setLoadingCharacters(false);
    }
  };

  // 加载章节列表
  const loadChapters = async () => {
    if (!novelId) return;
    
    setLoadingChapters(true);
    try {
      const response = await getNovelChaptersForRevision(novelId);
      setChapters(response.chapters);
    } catch (error) {
      console.error('加载章节列表失败:', error);
      message.error('加载章节列表失败');
    } finally {
      setLoadingChapters(false);
    }
  };

  // 处理需要选择目标的建议
  const handleSuggestionNeedsTarget = (suggestion: RevisionSuggestion) => {
    setPendingSuggestion(suggestion);
    setSelectedTargetId(null);
    
    if (suggestion.type === 'character') {
      loadCharacters();
      setCharacterSelectModalOpen(true);
    } else if (suggestion.type === 'chapter') {
      loadChapters();
      setChapterSelectModalOpen(true);
    }
  };

  // 应用单个建议（带目标选择）
  const handleApplySingleSuggestion = async (suggestion: RevisionSuggestion, targetId?: string) => {
    if (!novelId) {
      message.error('缺少小说ID');
      return;
    }
    
    // 如果是角色或章节建议，需要先选择目标
    if ((suggestion.type === 'character' || suggestion.type === 'chapter') && 
        !suggestion.target_id && !suggestion.target_name && !targetId) {
      handleSuggestionNeedsTarget(suggestion);
      return;
    }
    
    const suggestionToApply = { ...suggestion };
    if (targetId) {
      if (suggestion.type === 'character') {
        suggestionToApply.target_id = targetId;
      } else if (suggestion.type === 'chapter') {
        suggestionToApply.target_id = targetId;
      }
    }
    
    setApplyingSuggestions(true);
    try {
      const result = await applySuggestion({
        novel_id: novelId,
        suggestion: suggestionToApply
      });
      
      if (result.success) {
        message.success('建议应用成功！');
        // 关闭选择模态框
        setCharacterSelectModalOpen(false);
        setChapterSelectModalOpen(false);
        setPendingSuggestion(null);
      } else {
        message.error('应用失败，请稍后重试');
      }
    } catch (error) {
      console.error('应用建议失败:', error);
      message.error('应用建议失败，请重试');
    } finally {
      setApplyingSuggestions(false);
    }
  };

  // 批量应用选中的建议
  const handleApplySelectedSuggestions = async () => {
    if (!novelId || selectedSuggestions.length === 0) {
      message.warning('请选择要应用的建议');
      return;
    }
    
    const suggestionsToApply = selectedSuggestions.map(idx => suggestions[idx]);
    
    // 检查是否有需要选择目标的建议
    const needsTargetSelection = suggestionsToApply.some(
      s => (s.type === 'character' || s.type === 'chapter') && !s.target_id && !s.target_name
    );
    
    if (needsTargetSelection) {
      message.info('部分建议需要先选择具体的角色或章节，请逐个应用');
      return;
    }
    
    setApplyingSuggestions(true);
    try {
      const result = await applySuggestions({
        novel_id: novelId,
        suggestions: suggestionsToApply
      });
      
      if (result.success_count > 0) {
        message.success(`成功应用 ${result.success_count} 条建议`);
      }
      if (result.failed_count > 0) {
        message.warning(`${result.failed_count} 条建议应用失败`);
      }
      
      setSuggestionsModalOpen(false);
      setSuggestions([]);
      setSelectedSuggestions([]);
    } catch (error) {
      console.error('批量应用建议失败:', error);
      message.error('批量应用建议失败，请重试');
    } finally {
      setApplyingSuggestions(false);
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
          <Space orientation="vertical" style={{ width: '100%' }}>
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
            <Space style={{ marginTop: 8 }}>
              <Button size="small" icon={<HistoryOutlined />} onClick={() => {
                loadSessions();
                setHistoryModalOpen(true);
              }} />
              <Tooltip title="新建会话">
                <Button size="small" icon={<ReloadOutlined />} onClick={handleNewSession} />
              </Tooltip>
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
                      <div style={{ marginTop: 8, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                        <Tooltip title="智能提取建议并选择性应用">
                          <Button 
                            size="small" 
                            type="primary" 
                            icon={<EditOutlined />}
                            loading={extractingSuggestions}
                            onClick={() => handleExtractSuggestions(msg.content)}
                          >
                            提取建议
                          </Button>
                        </Tooltip>
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
                      <Typography.Text strong>
                        {session.title || (session.scene === 'novel_creation' ? '小说创作' : session.scene === 'novel_revision' ? '小说修订' : session.scene === 'novel_analysis' ? '小说分析' : '爬虫策略')}
                      </Typography.Text>
                      <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
                        {new Date(session.created_at).toLocaleString()}
                      </Typography.Text>
                    </div>
                  }
                  description={
                    <div>
                      <Tag color={
                        session.scene === 'novel_creation' ? 'blue' :
                        session.scene === 'novel_revision' ? 'green' :
                        session.scene === 'novel_analysis' ? 'orange' : 'purple'
                      }>
                        {session.scene === 'novel_creation' ? '创作' : 
                         session.scene === 'novel_revision' ? '修订' : 
                         session.scene === 'novel_analysis' ? '分析' : '爬虫'}
                      </Tag>
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

      {/* 建议选择模态框 */}
      <Modal
        title="AI修订建议"
        open={suggestionsModalOpen}
        onCancel={() => {
          setSuggestionsModalOpen(false);
          setSuggestions([]);
          setSelectedSuggestions([]);
        }}
        footer={[
          <Button key="cancel" onClick={() => {
            setSuggestionsModalOpen(false);
            setSuggestions([]);
            setSelectedSuggestions([]);
          }}>
            取消
          </Button>,
          <Button 
            key="apply" 
            type="primary"
            loading={applyingSuggestions}
            disabled={selectedSuggestions.length === 0}
            onClick={handleApplySelectedSuggestions}
          >
            应用选中的建议 ({selectedSuggestions.length})
          </Button>,
        ]}
        width={700}
      >
        <div style={{ marginBottom: 16 }}>
          <Typography.Text type="secondary">
            以下是从AI回复中提取的结构化修订建议，请选择要应用的建议：
          </Typography.Text>
        </div>
        <List
          dataSource={suggestions}
          renderItem={(suggestion, index) => (
            <List.Item
              style={{ 
                background: selectedSuggestions.includes(index) ? '#e6f7ff' : '#fafafa',
                marginBottom: 8,
                borderRadius: 8,
                padding: '12px 16px',
                cursor: 'pointer'
              }}
              onClick={() => {
                if (selectedSuggestions.includes(index)) {
                  setSelectedSuggestions(selectedSuggestions.filter(i => i !== index));
                } else {
                  setSelectedSuggestions([...selectedSuggestions, index]);
                }
              }}
            >
              <List.Item.Meta
                avatar={
                  <input 
                    type="checkbox" 
                    checked={selectedSuggestions.includes(index)}
                    onChange={() => {}}
                    style={{ transform: 'scale(1.2)' }}
                  />
                }
                title={
                  <Space>
                    <Tag color={
                      suggestion.type === 'world_setting' ? 'blue' :
                      suggestion.type === 'character' ? 'green' :
                      suggestion.type === 'outline' ? 'orange' :
                      suggestion.type === 'chapter' ? 'purple' : 'default'
                    }>
                      {suggestion.type === 'world_setting' ? '世界观' :
                       suggestion.type === 'character' ? '角色' :
                       suggestion.type === 'outline' ? '大纲' :
                       suggestion.type === 'chapter' ? '章节' : suggestion.type}
                    </Tag>
                    {suggestion.target_name && (
                      <Typography.Text strong>{suggestion.target_name}</Typography.Text>
                    )}
                    {suggestion.field && (
                      <Tag>{suggestion.field}</Tag>
                    )}
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      置信度: {Math.round(suggestion.confidence * 100)}%
                    </Typography.Text>
                  </Space>
                }
                description={
                  <div style={{ marginTop: 8 }}>
                    <Typography.Paragraph 
                      ellipsis={{ rows: 2, expandable: true }} 
                      style={{ marginBottom: 4 }}
                    >
                      {suggestion.description}
                    </Typography.Paragraph>
                    {suggestion.suggested_value && (
                      <Typography.Paragraph 
                        type="secondary"
                        ellipsis={{ rows: 2, expandable: true }}
                        style={{ fontSize: 12, marginBottom: 0 }}
                      >
                        建议内容: {suggestion.suggested_value}
                      </Typography.Paragraph>
                    )}
                  </div>
                }
              />
              <Button
                size="small"
                type="link"
                onClick={(e) => {
                  e.stopPropagation();
                  handleApplySingleSuggestion(suggestion);
                }}
              >
                单独应用
              </Button>
            </List.Item>
          )}
        />
        {suggestions.length === 0 && (
          <Typography.Text type="secondary" style={{ display: 'block', textAlign: 'center', padding: 20 }}>
            未提取到建议
          </Typography.Text>
        )}
      </Modal>

      {/* 角色选择模态框 */}
      <Modal
        title="选择要修改的角色"
        open={characterSelectModalOpen}
        onCancel={() => {
          setCharacterSelectModalOpen(false);
          setPendingSuggestion(null);
          setSelectedTargetId(null);
        }}
        footer={[
          <Button key="cancel" onClick={() => {
            setCharacterSelectModalOpen(false);
            setPendingSuggestion(null);
            setSelectedTargetId(null);
          }}>
            取消
          </Button>,
          <Button 
            key="apply" 
            type="primary"
            loading={applyingSuggestions}
            disabled={!selectedTargetId}
            onClick={() => {
              if (pendingSuggestion && selectedTargetId) {
                handleApplySingleSuggestion(pendingSuggestion, selectedTargetId);
              }
            }}
          >
            确认应用
          </Button>,
        ]}
        width={500}
      >
        <Spin spinning={loadingCharacters}>
          <Radio.Group 
            value={selectedTargetId} 
            onChange={(e) => setSelectedTargetId(e.target.value)}
            style={{ width: '100%' }}
          >
            <Space orientation="vertical" style={{ width: '100%' }}>
              {characters.map((char) => (
                <Radio key={char.id} value={char.id} style={{ width: '100%' }}>
                  <Card size="small" style={{ width: '100%', marginLeft: 8 }}>
                    <Space orientation="vertical" style={{ width: '100%' }}>
                      <Space>
                        <Typography.Text strong>{char.name}</Typography.Text>
                        {char.role_type && <Tag>{char.role_type}</Tag>}
                      </Space>
                      {char.personality && (
                        <Typography.Text type="secondary" ellipsis style={{ maxWidth: 350 }}>
                          性格: {char.personality}
                        </Typography.Text>
                      )}
                    </Space>
                  </Card>
                </Radio>
              ))}
            </Space>
          </Radio.Group>
          {!loadingCharacters && characters.length === 0 && (
            <Typography.Text type="secondary" style={{ display: 'block', textAlign: 'center', padding: 20 }}>
              暂无角色
            </Typography.Text>
          )}
        </Spin>
      </Modal>

      {/* 章节选择模态框 */}
      <Modal
        title="选择要修改的章节"
        open={chapterSelectModalOpen}
        onCancel={() => {
          setChapterSelectModalOpen(false);
          setPendingSuggestion(null);
          setSelectedTargetId(null);
        }}
        footer={[
          <Button key="cancel" onClick={() => {
            setChapterSelectModalOpen(false);
            setPendingSuggestion(null);
            setSelectedTargetId(null);
          }}>
            取消
          </Button>,
          <Button 
            key="apply" 
            type="primary"
            loading={applyingSuggestions}
            disabled={!selectedTargetId}
            onClick={() => {
              if (pendingSuggestion && selectedTargetId) {
                handleApplySingleSuggestion(pendingSuggestion, selectedTargetId);
              }
            }}
          >
            确认应用
          </Button>,
        ]}
        width={500}
      >
        <Spin spinning={loadingChapters}>
          <Radio.Group 
            value={selectedTargetId} 
            onChange={(e) => setSelectedTargetId(e.target.value)}
            style={{ width: '100%' }}
          >
            <Space orientation="vertical" style={{ width: '100%' }}>
              {chapters.map((chapter) => (
                <Radio key={chapter.id} value={String(chapter.chapter_number)} style={{ width: '100%' }}>
                  <Card size="small" style={{ width: '100%', marginLeft: 8 }}>
                    <Space>
                      <Typography.Text strong>第{chapter.chapter_number}章</Typography.Text>
                      {chapter.title && <Typography.Text>{chapter.title}</Typography.Text>}
                      <Typography.Text type="secondary">({chapter.word_count}字)</Typography.Text>
                      {chapter.status && <Tag>{chapter.status}</Tag>}
                    </Space>
                  </Card>
                </Radio>
              ))}
            </Space>
          </Radio.Group>
          {!loadingChapters && chapters.length === 0 && (
            <Typography.Text type="secondary" style={{ display: 'block', textAlign: 'center', padding: 20 }}>
              暂无章节
            </Typography.Text>
          )}
        </Spin>
      </Modal>
    </>
  );
}
