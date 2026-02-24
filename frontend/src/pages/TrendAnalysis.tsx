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
  Statistic,
} from 'antd';
import {
  LineChartOutlined,
  BarChartOutlined,
  ArrowUpOutlined,
  ReloadOutlined,
  BookOutlined,
  AlertOutlined,
} from '@ant-design/icons';
import {
  Line,
} from '@ant-design/charts';
import { getTrendAnalysis, getGenreTrendComparison, generateTrendReport } from '@/api/crawler';

const { Title, Text } = Typography;


export default function TrendAnalysis() {
  const [loading, setLoading] = useState(false);
  const [platform, setPlatform] = useState<string>('all');
  const [genre, setGenre] = useState<string>('all');
  const [metric, setMetric] = useState<string>('count');
  const [days, setDays] = useState<number>(90);
  const [forecastDays, setForecastDays] = useState<number>(90);
  const [trendData, setTrendData] = useState<any>(null);
  const [genreComparison, setGenreComparison] = useState<any>(null);
  const [trendReport, setTrendReport] = useState<any>(null);
  const [selectedGenres] = useState<string[]>(['玄幻', '都市', '科幻']);

  // 平台选项
  const platformOptions = [
    { value: 'all', label: '全部平台' },
    { value: 'qidian', label: '起点中文网' },
    { value: 'douyin', label: '抖音' },
    { value: 'fanqie', label: '番茄小说' },
    { value: 'zongheng', label: '纵横中文网' },
  ];

  // 指标选项
  const metricOptions = [
    { value: 'count', label: '作品数量' },
    { value: 'average_trend', label: '平均趋势' },
  ];

  // 分类选项
  const genreOptions = [
    { value: 'all', label: '全部分类' },
    { value: '玄幻', label: '玄幻' },
    { value: '都市', label: '都市' },
    { value: '科幻', label: '科幻' },
    { value: '仙侠', label: '仙侠' },
    { value: '历史', label: '历史' },
    { value: '悬疑', label: '悬疑' },
    { value: '游戏', label: '游戏' },
    { value: '轻小说', label: '轻小说' },
  ];

  // 获取趋势分析数据
  const fetchTrendData = async () => {
    setLoading(true);
    try {
      const res = await getTrendAnalysis({
        platform,
        genre,
        metric,
        days,
        forecast_days: forecastDays,
      });
      setTrendData(res.data);
    } catch (error) {
      console.error('获取趋势分析数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 获取分类趋势对比
  const fetchGenreComparison = async () => {
    setLoading(true);
    try {
      const res = await getGenreTrendComparison({
        genres: selectedGenres,
        days,
      });
      setGenreComparison(res.data);
    } catch (error) {
      console.error('获取分类趋势对比失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 获取趋势报告
  const fetchTrendReport = async () => {
    setLoading(true);
    try {
      const res = await generateTrendReport({
        platform,
        days,
        forecast_days: forecastDays,
      });
      setTrendReport(res.data);
    } catch (error) {
      console.error('获取趋势报告失败:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTrendData();
  }, [platform, genre, metric, days, forecastDays]);

  useEffect(() => {
    fetchGenreComparison();
  }, [selectedGenres, days]);

  useEffect(() => {
    fetchTrendReport();
  }, [platform, days, forecastDays]);

  // 准备图表数据

  // 时间序列数据
  const prepareTimeSeriesData = () => {
    if (!trendData) return [];
    
    const historicalData = trendData.historical_data || [];
    const predictions = trendData.predictions || [];
    
    return [...historicalData, ...predictions];
  };

  // 分类趋势对比数据
  const prepareGenreComparisonData = () => {
    if (!genreComparison?.comparison) return [];
    
    const data: any[] = [];
    Object.entries(genreComparison.comparison).forEach(([genre, analysis]) => {
        const historicalData = (analysis as any).historical_data || [];
        historicalData.forEach((item: any) => {
          data.push({
            date: item.date,
            genre,
            value: item.value,
          });
        });
      });
    
    return data;
  };

  // 趋势变化点数据
  const prepareTrendChangesData = () => {
    if (!trendData?.trend_changes) return [];
    return trendData.trend_changes;
  };

  // 图表配置

  // 时间序列图表配置
  const timeSeriesConfig = {
    data: prepareTimeSeriesData(),
    xField: 'date',
    yField: 'value',
    seriesField: 'is_prediction',
    smooth: true,
    lineStyle: {
      lineWidth: 2,
    },
    seriesStyle: {
      true: {
        stroke: '#ff4d4f',
        lineDash: [5, 5],
      },
      false: {
        stroke: '#1890ff',
      },
    },
    tooltip: {
      formatter: (datum: any) => {
        return {
          name: datum.date,
          value: datum.value.toFixed(2),
          prediction: datum.is_prediction ? '预测' : '历史',
        };
      },
    },
    annotations: [
      {
        type: 'text',
        position: ['min', 'max'],
        content: '预测数据',
        style: {
          fill: '#ff4d4f',
          fontSize: 12,
        },
      },
    ],
  };

  // 分类趋势对比图表配置
  const genreComparisonConfig = {
    data: prepareGenreComparisonData(),
    xField: 'date',
    yField: 'value',
    seriesField: 'genre',
    smooth: true,
    lineStyle: {
      lineWidth: 2,
    },
    tooltip: {
      formatter: (datum: any) => {
        return {
          name: `${datum.genre} - ${datum.date}`,
          value: datum.value.toFixed(2),
        };
      },
    },
  };



  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>
        <ArrowUpOutlined /> 趋势分析
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
          <Text strong>分类：</Text>
          <Select
            style={{ width: 150 }}
            value={genre}
            onChange={setGenre}
            options={genreOptions}
          />
          <Text strong>指标：</Text>
          <Select
            style={{ width: 120 }}
            value={metric}
            onChange={setMetric}
            options={metricOptions}
          />
          <Text strong>分析天数：</Text>
          <Select
            style={{ width: 100 }}
            value={days}
            onChange={setDays}
            options={[
              { value: 30, label: '30天' },
              { value: 60, label: '60天' },
              { value: 90, label: '90天' },
            ]}
          />
          <Text strong>预测天数：</Text>
          <Select
            style={{ width: 100 }}
            value={forecastDays}
            onChange={setForecastDays}
            options={[
              { value: 30, label: '30天' },
              { value: 60, label: '60天' },
              { value: 90, label: '90天' },
            ]}
          />
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            onClick={fetchTrendData}
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
      ) : !trendData ? (
        <Alert
          title="暂无数据"
          description="请尝试调整筛选条件或稍后再试"
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
      ) : (
        <>
          {/* 统计卡片 */}
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}>
              <Card size="small">
                <Statistic
                  title="趋势方向"
                  value={trendData.statistics?.trend_direction || '稳定'}
                  prefix={
                    trendData.statistics?.trend_direction === 'increasing' ? (
                      <ArrowUpOutlined style={{ color: '#52c41a' }} />
                    ) : trendData.statistics?.trend_direction === 'decreasing' ? (
                      <ArrowUpOutlined style={{ color: '#ff4d4f', transform: 'rotate(180deg)' }} />
                    ) : (
                      <ArrowUpOutlined style={{ color: '#faad14' }} />
                    )
                  }
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small">
                <Statistic
                  title="平均数值"
                  value={trendData.statistics?.average_value?.toFixed(2) || '0'}
                  suffix={metric === 'count' ? '个' : '分'}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small">
                <Statistic
                  title="趋势斜率"
                  value={trendData.statistics?.slope?.toFixed(4) || '0'}
                  suffix={trendData.statistics?.slope > 0 ? '上升' : '下降'}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small">
                <Statistic
                  title="变化点数量"
                  value={trendData.trend_changes?.length || 0}
                  prefix={<AlertOutlined />}
                />
              </Card>
            </Col>
          </Row>

          <Tabs
          defaultActiveKey="time-series"
          style={{ marginBottom: 16 }}
          tabPlacement="top"
          items={[
            {
              key: 'time-series',
              label: (
                <Space>
                  <LineChartOutlined />
                  <Text>时间序列</Text>
                </Space>
              ),
              children: (
                <Card title="趋势分析与预测" style={{ height: 400 }}>
                  <Line {...timeSeriesConfig} style={{ width: '100%', height: '100%' }} />
                </Card>
              ),
            },
            {
              key: 'genre-comparison',
              label: (
                <Space>
                  <BarChartOutlined />
                  <Text>分类对比</Text>
                </Space>
              ),
              children: (
                <Card title="分类趋势对比" style={{ height: 400 }}>
                  <Line {...genreComparisonConfig} style={{ width: '100%', height: '100%' }} />
                </Card>
              ),
            },
            {
              key: 'trend-changes',
              label: (
                <Space>
                  <AlertOutlined />
                  <Text>变化分析</Text>
                </Space>
              ),
              children: (
                <Card title="趋势变化点分析">
                  {prepareTrendChangesData().length > 0 ? (
                    <Row gutter={16}>
                      {prepareTrendChangesData().map((change: any, index: number) => (
                        <Col span={8} key={index}>
                          <Card size="small" bordered={false}>
                            <Text strong>{change.date}</Text>
                            <div style={{ marginTop: 8 }}>
                              <Text type={change.change_type === 'increase' ? 'success' : 'danger'}>
                                {change.change_type === 'increase' ? '上升' : '下降'} {Math.abs(change.change_ratio * 100).toFixed(1)}%
                              </Text>
                            </div>
                            <div style={{ marginTop: 4, fontSize: 12, color: '#666' }}>
                              从 {change.previous_value.toFixed(2)} 到 {change.current_value.toFixed(2)}
                            </div>
                          </Card>
                        </Col>
                      ))}
                    </Row>
                  ) : (
                    <Alert
                      title="暂无变化点"
                      description="在所选时间范围内未检测到显著的趋势变化"
                      type="info"
                      showIcon
                    />
                  )}
                </Card>
              ),
            },
            {
              key: 'trend-report',
              label: (
                <Space>
                  <BookOutlined />
                  <Text>趋势报告</Text>
                </Space>
              ),
              children: trendReport ? (
                  <Card title="趋势分析报告">
                    <div style={{ marginBottom: 16 }}>
                      <Text strong>生成时间：</Text>
                      <Text>{trendReport.generated_at}</Text>
                    </div>
                    <div style={{ marginBottom: 16 }}>
                      <Text strong>分析平台：</Text>
                      <Text>{trendReport.platform === 'all' ? '全部平台' : trendReport.platform}</Text>
                    </div>
                    <div style={{ marginBottom: 16 }}>
                      <Text strong>分析天数：</Text>
                      <Text>{trendReport.days_analyzed}天</Text>
                    </div>
                    <div style={{ marginBottom: 16 }}>
                      <Text strong>预测天数：</Text>
                      <Text>{trendReport.forecast_days}天</Text>
                    </div>
                    {trendReport.hot_trends && trendReport.hot_trends.length > 0 && (
                      <div style={{ marginBottom: 16 }}>
                        <Text strong>热门趋势：</Text>
                        <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                          {trendReport.hot_trends.map((trend: any, index: number) => (
                            <li key={index} style={{ marginBottom: 4 }}>
                              <Text>{index + 1}. {trend.genre} - 增长斜率: {trend.slope.toFixed(4)}</Text>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {trendReport.recommendations && trendReport.recommendations.length > 0 && (
                      <div>
                        <Text strong>建议：</Text>
                        <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                          {trendReport.recommendations.map((rec: string, index: number) => (
                            <li key={index} style={{ marginBottom: 4 }}>
                              <Text>{rec}</Text>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </Card>
                ) : (
                  <div style={{ textAlign: 'center', padding: '40px 0' }}>
                    <Button
                      type="primary"
                      icon={<ReloadOutlined />}
                      onClick={fetchTrendReport}
                    >
                      生成趋势报告
                    </Button>
                  </div>
                )
            },
          ]}
          />
        </>
      )}
    </div>
  );
}
