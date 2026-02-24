import { useState, useEffect } from 'react';
import {
  Card,
  Row,
  Col,
  Select,
  Space,
  Button,
  Tabs,
  Spin,
  Typography,
  Alert,
} from 'antd';
import {
  BarChartOutlined,
  LineChartOutlined,
  PieChartOutlined,
  RadarChartOutlined,
  HeatMapOutlined,
  ReloadOutlined,
  BookOutlined,
} from '@ant-design/icons';
import {
  Bar,
  Line,
  Pie,
  Radar,
  Heatmap,
} from '@ant-design/charts';
import { getReaderPreferences, getTrendingTags, getRecommendedGenres } from '@/api/crawler';

const { Title, Text } = Typography;
const { TabPane } = Tabs;

export default function ChartAnalysis() {
  const [loading, setLoading] = useState(false);
  const [platform, setPlatform] = useState<string>('all');
  const [days, setDays] = useState<number>(30);
  const [preferenceData, setPreferenceData] = useState<any>(null);
  const [trendingTags, setTrendingTags] = useState<any[]>([]);
  const [recommendedGenres, setRecommendedGenres] = useState<any[]>([]);

  // 平台选项
  const platformOptions = [
    { value: 'all', label: '全部平台' },
    { value: 'qidian', label: '起点中文网' },
    { value: 'douyin', label: '抖音' },
    { value: 'fanqie', label: '番茄小说' },
    { value: 'zongheng', label: '纵横中文网' },
  ];

  // 获取数据
  const fetchData = async () => {
    setLoading(true);
    try {
      // 获取读者偏好数据
      const prefRes = await getReaderPreferences({ platform, days });
      setPreferenceData(prefRes.data);

      // 获取热门标签
      const tagsRes = await getTrendingTags({ platform, days, limit: 20 });
      setTrendingTags(tagsRes.data);

      // 获取推荐分类
      const genresRes = await getRecommendedGenres({ platform, days, limit: 10 });
      setRecommendedGenres(genresRes.data);
    } catch (error) {
      console.error('获取图表数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [platform, days]);

  // 准备图表数据

  // 分类分布数据（柱状图）
  const genreDistributionData = () => {
    if (!preferenceData?.genre_distribution) return [];
    return Object.entries(preferenceData.genre_distribution).map(([genre, count]) => ({
      genre,
      count: Number(count),
    })).sort((a, b) => b.count - a.count).slice(0, 10);
  };

  // 平台分布数据（饼图）
  const platformDistributionData = () => {
    if (!preferenceData?.platform_distribution) return [];
    return Object.entries(preferenceData.platform_distribution).map(([platform, count]) => {
      const platformMap: Record<string, string> = {
        'qidian': '起点',
        'douyin': '抖音',
        'fanqie': '番茄',
        'zongheng': '纵横',
      };
      return {
        platform: platformMap[platform] || platform,
        count: Number(count),
      };
    });
  };

  // 热门标签数据（柱状图）
  const tagsData = () => {
    return trendingTags.slice(0, 15).map(tag => ({
      tag: tag.tag,
      count: tag.count,
    }));
  };

  // 分类热度数据（雷达图）
  const genreHeatData = () => {
    if (!recommendedGenres.length) return [];
    return recommendedGenres.slice(0, 6).map(genre => ({
      genre: genre.genre,
      heat: genre.heat_score || 0,
      rating: genre.average_rating || 0,
      trend: genre.average_trend_score || 0,
    }));
  };

  // 时间趋势数据（折线图）
  const temporalTrendData = () => {
    if (!preferenceData?.temporal_trends) return [];
    return Object.entries(preferenceData.temporal_trends).map(([date, data]) => ({
      date,
      count: (data as any).count,
      average_trend: (data as any).average_trend || 0,
    })).sort((a, b) => a.date.localeCompare(b.date));
  };

  // 热力图数据（模拟）
  const heatmapData = () => {
    if (!recommendedGenres.length) return [];
    const genres = recommendedGenres.slice(0, 8).map(g => g.genre);
    const platforms = ['qidian', 'douyin', 'fanqie', 'zongheng'];
    const platformMap: Record<string, string> = {
      'qidian': '起点',
      'douyin': '抖音',
      'fanqie': '番茄',
      'zongheng': '纵横',
    };
    
    const data = [];
    for (const genre of genres) {
      for (const platform of platforms) {
        data.push({
          genre,
          platform: platformMap[platform],
          value: Math.random() * 100,
        });
      }
    }
    return data;
  };

  // 图表配置

  // 柱状图配置
  const barConfig = {
    data: genreDistributionData(),
    xField: 'genre',
    yField: 'count',
    label: {
      position: 'top',
    },
    tooltip: {
      formatter: (datum: any) => {
        return {
          name: datum.genre,
          value: datum.count,
        };
      },
    },
    style: {
      fill: '#1890ff',
    },
  };



  // 饼图配置
  const pieConfig = {
    data: platformDistributionData(),
    angleField: 'count',
    colorField: 'platform',
    radius: 0.8,
    label: {
      type: 'outer',
      content: '{name}: {percentage}',
    },
    interactions: [
      {
        type: 'element-active',
      },
    ],
  };

  // 雷达图配置
  const radarConfig = {
    data: genreHeatData(),
    xField: 'genre',
    yField: ['heat', 'rating', 'trend'],
    meta: {
      heat: {
        alias: '热度',
      },
      rating: {
        alias: '评分',
      },
      trend: {
        alias: '趋势',
      },
    },
  };

  // 热力图配置
  const heatmapConfig = {
    data: heatmapData(),
    xField: 'platform',
    yField: 'genre',
    colorField: 'value',
    label: {
      style: {
        fill: '#fff',
      },
    },
    tooltip: {
      formatter: (datum: any) => {
        return {
          name: `${datum.genre} - ${datum.platform}`,
          value: datum.value.toFixed(2),
        };
      },
    },
    color: ['#bae7ff', '#1890ff', '#0050b3'],
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>
        <BookOutlined /> 图表分析
      </Title>

      {/* 筛选条件 */}
      <Card style={{ marginBottom: 16 }}>
        <Space size="middle">
          <Text strong>平台：</Text>
          <Select
            style={{ width: 150 }}
            value={platform}
            onChange={setPlatform}
            options={platformOptions}
          />
          <Text strong>分析天数：</Text>
          <Select
            style={{ width: 100 }}
            value={days}
            onChange={setDays}
            options={[
              { value: 7, label: '7天' },
              { value: 30, label: '30天' },
              { value: 90, label: '90天' },
            ]}
          />
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            onClick={fetchData}
            loading={loading}
          >
            刷新数据
          </Button>
        </Space>
      </Card>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin size="large" description="加载数据中..." />
        </div>
      ) : !preferenceData ? (
        <Alert
          title="暂无数据"
          description="请尝试调整筛选条件或稍后再试"
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
      ) : (
        <Tabs
          defaultActiveKey="bar"
          style={{ marginBottom: 16 }}
          tabPlacement="top"
          items={[
            {
              key: 'bar',
              label: (
                <Space>
                  <BarChartOutlined />
                  <Text>分类分布</Text>
                </Space>
              ),
              children: (
                <Row gutter={16}>
                  <Col span={24}>
                    <Card title="分类分布" style={{ height: 400 }}>
                      <Bar {...barConfig} style={{ width: '100%', height: '100%' }} />
                    </Card>
                  </Col>
                  <Col span={24} style={{ marginTop: 16 }}>
                    <Card title="热门标签" style={{ height: 400 }}>
                      <Bar
                        data={tagsData()}
                        xField="tag"
                        yField="count"
                        label={{ position: 'top' }}
                        tooltip={{}}
                        style={{ fill: '#722ed1', width: '100%', height: '100%' }}
                      />
                    </Card>
                  </Col>
                </Row>
              ),
            },
            {
              key: 'line',
              label: (
                <Space>
                  <LineChartOutlined />
                  <Text>趋势分析</Text>
                </Space>
              ),
              children: (
                <Card title="时间趋势" style={{ height: 400 }}>
                  <Line
                    data={temporalTrendData()}
                    xField="date"
                    yField="count"
                    smooth
                    tooltip={{}}
                    style={{ stroke: '#52c41a', lineWidth: 2, width: '100%', height: '100%' }}
                  />
                </Card>
              ),
            },
            {
              key: 'pie',
              label: (
                <Space>
                  <PieChartOutlined />
                  <Text>平台分布</Text>
                </Space>
              ),
              children: (
                <Row gutter={16}>
                  <Col span={12}>
                    <Card title="平台分布" style={{ height: 400 }}>
                      <Pie {...pieConfig} style={{ width: '100%', height: '100%' }} />
                    </Card>
                  </Col>
                  <Col span={12}>
                    <Card title="分类占比" style={{ height: 400 }}>
                      <Pie
                        data={genreDistributionData()}
                        angleField="count"
                        colorField="genre"
                        radius={0.8}
                        label={{ type: 'outer' }}
                        style={{ width: '100%', height: '100%' }}
                      />
                    </Card>
                  </Col>
                </Row>
              ),
            },
            {
              key: 'radar',
              label: (
                <Space>
                  <RadarChartOutlined />
                  <Text>分类雷达</Text>
                </Space>
              ),
              children: (
                <Card title="分类多维度分析" style={{ height: 400 }}>
                  <Radar {...radarConfig} style={{ width: '100%', height: '100%' }} />
                </Card>
              ),
            },
            {
              key: 'heatmap',
              label: (
                <Space>
                  <HeatMapOutlined />
                  <Text>热力图</Text>
                </Space>
              ),
              children: (
                <Card title="分类-平台热力图" style={{ height: 400 }}>
                  <Heatmap {...heatmapConfig} style={{ width: '100%', height: '100%' }} />
                </Card>
              ),
            },
          ]}
        />
      )}
    </div>
  );
}