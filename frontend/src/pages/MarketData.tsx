import { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Select,
  Space,
  Tag,
  Typography,
  Row,
  Col,
  Statistic,
  InputNumber,
  Button,
} from 'antd';
import {
  SearchOutlined,
  ReloadOutlined,
  BookOutlined,
  UserOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { MarketDataItem } from '@/api/types';
import { getMarketData } from '@/api/crawler';

const { Text, Title } = Typography;

export default function MarketData() {
  const [data, setData] = useState<MarketDataItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [genre, setGenre] = useState<string | undefined>();
  const [minWordCount, setMinWordCount] = useState<number | undefined>();
  const [maxWordCount, setMaxWordCount] = useState<number | undefined>();

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await getMarketData({
        platform: 'qidian',
        genre,
        min_word_count: minWordCount,
        max_word_count: maxWordCount,
        page,
        page_size: pageSize,
      });
      setData(res.items);
      setTotal(res.total);
    } catch {
      // Error handled silently
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [page, pageSize]);

  const handleSearch = () => {
    setPage(1);
    fetchData();
  };

  const formatWordCount = (count: number | null) => {
    if (!count) return '-';
    if (count >= 10000) {
      return `${(count / 10000).toFixed(1)}万字`;
    }
    return `${count}字`;
  };

  const columns: ColumnsType<MarketDataItem> = [
    {
      title: '书名',
      dataIndex: 'book_title',
      key: 'book_title',
      width: 200,
      render: (v, record) => (
        <Space direction="vertical" size={0}>
          <Text strong>{v || '-'}</Text>
          {record.author_name && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              <UserOutlined /> {record.author_name}
            </Text>
          )}
        </Space>
      ),
    },
    {
      title: '类型',
      dataIndex: 'genre',
      key: 'genre',
      width: 100,
      render: (v) => v ? <Tag color="blue">{v}</Tag> : '-',
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      width: 200,
      render: (tags: string[] | null) => (
        tags && tags.length > 0 ? (
          <Space wrap size={[4, 4]}>
            {tags.slice(0, 3).map((tag, i) => (
              <Tag key={i}>{tag}</Tag>
            ))}
            {tags.length > 3 && <Text type="secondary">+{tags.length - 3}</Text>}
          </Space>
        ) : '-'
      ),
    },
    {
      title: '字数',
      dataIndex: 'word_count',
      key: 'word_count',
      width: 100,
      render: formatWordCount,
      sorter: (a, b) => (a.word_count || 0) - (b.word_count || 0),
    },
    {
      title: '评分',
      dataIndex: 'rating',
      key: 'rating',
      width: 80,
      render: (v) => v ? <Text style={{ color: '#faad14' }}>{v.toFixed(1)}</Text> : '-',
      sorter: (a, b) => (a.rating || 0) - (b.rating || 0),
    },
    {
      title: '趋势评分',
      dataIndex: 'trend_score',
      key: 'trend_score',
      width: 100,
      render: (v) => v ? <Text style={{ color: '#52c41a' }}>{v.toFixed(2)}</Text> : '-',
      sorter: (a, b) => (a.trend_score || 0) - (b.trend_score || 0),
    },
    {
      title: '数据日期',
      dataIndex: 'data_date',
      key: 'data_date',
      width: 120,
      render: (v) => v || '-',
    },
  ];

  // 统计数据
  const avgWordCount = data.length > 0
    ? Math.round(data.reduce((sum, item) => sum + (item.word_count || 0), 0) / data.length)
    : 0;
  const avgRating = data.length > 0
    ? (data.reduce((sum, item) => sum + (item.rating || 0), 0) / data.filter(d => d.rating).length).toFixed(2)
    : '0';

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>
        <BookOutlined /> 市场数据分析
      </Title>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="数据总量"
              value={total}
              prefix={<FileTextOutlined />}
              suffix="条"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="平均字数"
              value={avgWordCount >= 10000 ? (avgWordCount / 10000).toFixed(1) : avgWordCount}
              suffix={avgWordCount >= 10000 ? '万字' : '字'}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="平均评分"
              value={avgRating}
              precision={2}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="数据来源"
              value="起点中文网"
            />
          </Card>
        </Col>
      </Row>

      {/* 筛选和数据表 */}
      <Card>
        <Space style={{ marginBottom: 16 }} wrap>
          <Select
            placeholder="选择类型"
            allowClear
            style={{ width: 150 }}
            value={genre}
            onChange={setGenre}
            options={[
              { value: '玄幻', label: '玄幻' },
              { value: '奇幻', label: '奇幻' },
              { value: '武侠', label: '武侠' },
              { value: '仙侠', label: '仙侠' },
              { value: '都市', label: '都市' },
              { value: '现实', label: '现实' },
              { value: '军事', label: '军事' },
              { value: '历史', label: '历史' },
              { value: '游戏', label: '游戏' },
              { value: '体育', label: '体育' },
              { value: '科幻', label: '科幻' },
              { value: '悬疑', label: '悬疑' },
              { value: '轻小说', label: '轻小说' },
            ]}
          />
          <InputNumber
            placeholder="最小字数(万)"
            style={{ width: 130 }}
            value={minWordCount ? minWordCount / 10000 : undefined}
            onChange={(v) => setMinWordCount(v ? v * 10000 : undefined)}
            min={0}
          />
          <InputNumber
            placeholder="最大字数(万)"
            style={{ width: 130 }}
            value={maxWordCount ? maxWordCount / 10000 : undefined}
            onChange={(v) => setMaxWordCount(v ? v * 10000 : undefined)}
            min={0}
          />
          <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
            搜索
          </Button>
          <Button icon={<ReloadOutlined />} onClick={fetchData}>
            刷新
          </Button>
        </Space>

        <Table
          columns={columns}
          dataSource={data}
          rowKey={(record) => record.book_id || Math.random().toString()}
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
          size="middle"
        />
      </Card>
    </div>
  );
}
