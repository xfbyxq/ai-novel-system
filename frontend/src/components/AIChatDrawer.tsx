import { useEffect, useRef, useState } from 'react';
import {
  Drawer, Input, Button, Typography, Spin, Space, Divider,
} from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, ReloadOutlined } from '@ant-design/icons';
import { createChatSession, getWebSocketUrl, sendChatMessage } from '@/api/aiChat';

const { TextArea } = Input;

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  scene: 'novel_creation' | 'crawler_task';
}

export default function AIChatDrawer({ open, onClose, scene }: Props) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const initSession = async () => {
    try {
      const response = await createChatSession({ scene });
      setSessionId(response.session_id);
      setMessages([{ role: 'assistant', content: response.welcome_message }]);
    } catch (error) {
      console.error('创建会话失败:', error);
    }
  };

  useEffect(() => {
    if (open && !sessionId) {
      initSession();
    }
  }, [open, sessionId, scene]);

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

  const title = scene === 'novel_creation' ? '小说创作助手' : '爬虫策略助手';

  return (
    <Drawer
      title={
        <Space>
          <RobotOutlined />
          <span>{title}</span>
          <Button size="small" icon={<ReloadOutlined />} onClick={handleRestart} />
        </Space>
      }
      placement="right"
      width={480}
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
  );
}
