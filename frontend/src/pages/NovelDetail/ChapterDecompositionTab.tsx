import { useState, useCallback, useEffect } from 'react';
import {
  Card,
  Typography,
  Button,
  Space,
  Row,
  Col,
  Collapse,
  Tag,
  Tooltip,
  message,
  Slider,
  InputNumber,
  Divider,
  Spin,
  Empty,
  Input,
} from 'antd';
import {
  DragOutlined,
  SaveOutlined,
  CheckCircleOutlined,
  PlusOutlined,
  DeleteOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { Select } from 'antd';
import type { PlotOutline } from '@/api/types';
import { getPlotOutline, updatePlotOutline } from '@/api/outlines';

interface Volume {
  volume_num: number;
  title: string;
  summary: string;
  chapter_start: number;
  chapter_end: number;
  main_events?: string[];
  side_plots?: string[];
  tension_cycle?: string;
  foreshadowing?: string[];
  key?: string;
}

interface ChapterDecomposition {
  total_volumes: number;
  total_chapters: number;
  volumes: Volume[];
}

interface Props {
  novelId: string;
  onDecompositionConfirm?: (data: ChapterDecomposition) => void;
}

const DEFAULT_CHAPTERS_PER_VOLUME = 10;
const MIN_CHAPTERS_PER_VOLUME = 5;
const MAX_CHAPTERS_PER_VOLUME = 20;

export default function ChapterDecompositionTab({ novelId, onDecompositionConfirm }: Props) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [outline, setOutline] = useState<PlotOutline | null>(null);

  const [decomposition, setDecomposition] = useState<ChapterDecomposition | null>(null);
  const [draggedVolumeIndex, setDraggedVolumeIndex] = useState<number | null>(null);

  const fetchOutline = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getPlotOutline(novelId);
      
      const volumes = (data.volumes || []) as unknown[];
      
      if (volumes.length > 0) {
        const existingDecomposition: ChapterDecomposition = {
          total_volumes: volumes.length,
          total_chapters: 0,
          volumes: [],
        };

        let chapterCounter = 1;
        volumes.forEach((vol: any, index: number) => {
          const chapterCount = DEFAULT_CHAPTERS_PER_VOLUME;
          const volume: Volume = {
            volume_num: (vol.volume_num as number) || index + 1,
            title: (vol.title as string) || `第${index + 1}卷`,
            summary: (vol.summary as string) || '',
            chapter_start: chapterCounter,
            chapter_end: chapterCounter + chapterCount - 1,
            main_events: (vol.main_events as string[]) || [],
            side_plots: [],
            tension_cycle: 'rising',
            foreshadowing: [],
            key: `vol-${index}`,
          };
          
          existingDecomposition.volumes.push(volume);
          existingDecomposition.total_chapters += chapterCount;
          chapterCounter += chapterCount;
        });

        setDecomposition(existingDecomposition);
      } else {
        const defaultDecomposition: ChapterDecomposition = {
          total_volumes: 3,
          total_chapters: 30,
          volumes: [],
        };

        for (let i = 0; i < 3; i++) {
          const chapterStart = i * DEFAULT_CHAPTERS_PER_VOLUME + 1;
          defaultDecomposition.volumes.push({
            volume_num: i + 1,
            title: `第${i + 1}卷`,
            summary: '',
            chapter_start: chapterStart,
            chapter_end: chapterStart + DEFAULT_CHAPTERS_PER_VOLUME - 1,
            main_events: [],
            side_plots: [],
            tension_cycle: i === 0 ? 'rising' : i === 1 ? 'climax' : 'falling',
            foreshadowing: [],
            key: `vol-${i}`,
          });
        }

        setDecomposition(defaultDecomposition);
      }
    } catch (error) {
      console.error('Failed to fetch outline:', error);
      message.error('加载大纲失败');
    } finally {
      setLoading(false);
    }
  }, [novelId]);

  useEffect(() => {
    void fetchOutline();
  }, [fetchOutline]);

  const handleVolumeChange = useCallback((
    index: number,
    field: keyof Volume,
    value: unknown
  ) => {
    if (!decomposition) return;

    const newVolumes = [...decomposition.volumes];
    newVolumes[index] = { ...newVolumes[index], [field]: value };

    let newTotalChapters = 0;
    let chapterCounter = 1;

    newVolumes.forEach((vol) => {
      const chapterCount = vol.chapter_end - vol.chapter_start + 1;
      vol.chapter_start = chapterCounter;
      vol.chapter_end = chapterCounter + chapterCount - 1;
      newTotalChapters += chapterCount;
      chapterCounter += chapterCount;
    });

    setDecomposition({
      ...decomposition,
      volumes: newVolumes,
      total_chapters: newTotalChapters,
    });
  }, [decomposition]);

  const handleAddVolume = useCallback(() => {
    if (!decomposition) return;

    const newVolumeNum = decomposition.volumes.length + 1;
    const lastVolume = decomposition.volumes[decomposition.volumes.length - 1];
    const chapterStart = lastVolume ? lastVolume.chapter_end + 1 : 1;
    const chapterEnd = chapterStart + DEFAULT_CHAPTERS_PER_VOLUME - 1;

    const newVolume: Volume = {
      volume_num: newVolumeNum,
      title: `第${newVolumeNum}卷`,
      summary: '',
      chapter_start: chapterStart,
      chapter_end: chapterEnd,
      main_events: [],
      side_plots: [],
      tension_cycle: 'rising',
      foreshadowing: [],
      key: `vol-${decomposition.volumes.length}`,
    };

    setDecomposition({
      ...decomposition,
      volumes: [...decomposition.volumes, newVolume],
      total_volumes: decomposition.volumes.length + 1,
      total_chapters: decomposition.total_chapters + DEFAULT_CHAPTERS_PER_VOLUME,
    });

    message.success('已添加新卷');
  }, [decomposition]);

  const handleDeleteVolume = useCallback((index: number) => {
    if (!decomposition || decomposition.volumes.length <= 1) {
      message.warning('至少需要保留一卷');
      return;
    }

    const newVolumes = decomposition.volumes.filter((_, i) => i !== index);
    
    let newTotalChapters = 0;
    let chapterCounter = 1;

    newVolumes.forEach((vol, i) => {
      const chapterCount = vol.chapter_end - vol.chapter_start + 1;
      vol.chapter_start = chapterCounter;
      vol.chapter_end = chapterCounter + chapterCount - 1;
      vol.volume_num = i + 1;
      vol.key = `vol-${i}`;
      newTotalChapters += chapterCount;
      chapterCounter += chapterCount;
    });

    setDecomposition({
      ...decomposition,
      volumes: newVolumes,
      total_volumes: newVolumes.length,
      total_chapters: newTotalChapters,
    });

    message.success('已删除卷');
  }, [decomposition]);

  const handleDragStart = useCallback((index: number) => {
    setDraggedVolumeIndex(index);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  const handleDrop = useCallback((dropIndex: number) => {
    if (!decomposition || draggedVolumeIndex === null || draggedVolumeIndex === dropIndex) {
      setDraggedVolumeIndex(null);
      return;
    }

    const newVolumes = [...decomposition.volumes];
    const [draggedVolume] = newVolumes.splice(draggedVolumeIndex, 1);
    newVolumes.splice(dropIndex, 0, draggedVolume);

    newVolumes.forEach((vol, i) => {
      vol.volume_num = i + 1;
      vol.key = `vol-${i}`;
    });

    let chapterCounter = 1;
    let newTotalChapters = 0;

    newVolumes.forEach((vol) => {
      const chapterCount = vol.chapter_end - vol.chapter_start + 1;
      vol.chapter_start = chapterCounter;
      vol.chapter_end = chapterCounter + chapterCount - 1;
      newTotalChapters += chapterCount;
      chapterCounter += chapterCount;
    });

    setDecomposition({
      ...decomposition,
      volumes: newVolumes,
      total_chapters: newTotalChapters,
    });

    setDraggedVolumeIndex(null);
    message.success('卷顺序已调整');
  }, [decomposition, draggedVolumeIndex]);

  const handleSaveConfiguration = useCallback(async () => {
    if (!decomposition) return;

    console.log('🎯 开始保存配置:', { novelId, decomposition });
    
    setSaving(true);
    try {
      const volumesData = decomposition.volumes.map((vol) => ({
        volume_num: vol.volume_num,
        title: vol.title,
        summary: vol.summary,
        chapter_range: [vol.chapter_start, vol.chapter_end],
        main_events: vol.main_events,
        side_plots: vol.side_plots,
        tension_cycle: vol.tension_cycle,
        foreshadowing: vol.foreshadowing,
      }));

      console.log('📤 发送的数据:', { 
        novelId, 
        volumes: volumesData 
      });

      await updatePlotOutline(novelId, {
        volumes: volumesData as unknown[],
      });

      // 保存成功后重新获取最新数据
      await fetchOutline();

      console.log('✅ 配置保存成功');
      message.success('配置已保存');
      onDecompositionConfirm?.(decomposition);
    } catch (error) {
      console.error('❌ 保存配置错误:', error);
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  }, [novelId, decomposition, onDecompositionConfirm]);

  const handleConfirmDecomposition = useCallback(async () => {
    if (!decomposition) return;

    if (decomposition.total_chapters < decomposition.total_volumes * MIN_CHAPTERS_PER_VOLUME) {
      message.warning('每卷至少需要 5 章');
      return;
    }

    await handleSaveConfiguration();
    message.success('章节拆分已确认');
  }, [decomposition, handleSaveConfiguration]);

  const handleChapterCountChange = useCallback((volumeIndex: number, newCount: number) => {
    if (!decomposition) return;

    const clampedCount = Math.max(
      MIN_CHAPTERS_PER_VOLUME,
      Math.min(newCount, MAX_CHAPTERS_PER_VOLUME)
    );

    const newVolumes = [...decomposition.volumes];
    const volume = { ...newVolumes[volumeIndex] };
    
    volume.chapter_end = volume.chapter_start + clampedCount - 1;
    newVolumes[volumeIndex] = volume;

    let chapterCounter = 1;
    let newTotalChapters = 0;

    newVolumes.forEach((vol) => {
      const chapterCount = vol.chapter_end - vol.chapter_start + 1;
      vol.chapter_start = chapterCounter;
      vol.chapter_end = chapterCounter + chapterCount - 1;
      newTotalChapters += chapterCount;
      chapterCounter += chapterCount;
    });

    setDecomposition({
      ...decomposition,
      volumes: newVolumes,
      total_chapters: newTotalChapters,
    });
  }, [decomposition]);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" />
        <Typography.Text style={{ display: 'block', marginTop: 16 }}>
          正在加载章节拆分配置...
        </Typography.Text>
      </div>
    );
  }

  if (!decomposition) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description="暂无章节拆分数据"
      >
        <Button type="primary" onClick={() => void fetchOutline()}>
          重新加载
        </Button>
      </Empty>
    );
  }

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Row align="middle" justify="space-between">
          <Col>
            <Space orientation="horizontal" size="large">
              <div>
                <Typography.Text type="secondary">总卷数</Typography.Text>
                <Typography.Title level={4} style={{ margin: 0 }}>
                  {decomposition.total_volumes} 卷
                </Typography.Title>
              </div>
              <div>
                <Typography.Text type="secondary">总章节数</Typography.Text>
                <Typography.Title level={4} style={{ margin: 0 }}>
                  {decomposition.total_chapters} 章
                </Typography.Title>
              </div>
              <div>
                <Typography.Text type="secondary">平均每卷</Typography.Text>
                <Typography.Title level={4} style={{ margin: 0 }}>
                  {Math.round(decomposition.total_chapters / decomposition.total_volumes)} 章
                </Typography.Title>
              </div>
            </Space>
          </Col>
          <Col>
            <Space>
              <Button
                icon={<PlusOutlined />}
                onClick={handleAddVolume}
              >
                添加卷
              </Button>
              <Button
                icon={<SaveOutlined />}
                onClick={handleSaveConfiguration}
                loading={saving}
              >
                保存配置
              </Button>
              <Button
                type="primary"
                icon={<CheckCircleOutlined />}
                onClick={handleConfirmDecomposition}
                loading={saving}
              >
                确认章节拆分
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Collapse
        defaultActiveKey={decomposition.volumes.map((_, i) => `vol-${i}`)}
        accordion={false}
        items={decomposition.volumes.map((volume, index) => ({
          key: volume.key,
          label: (
            <Row align="middle" gutter={16} style={{ width: '100%' }}>
              <Col>
                <DragOutlined
                  style={{ cursor: 'grab', color: '#999' }}
                  onMouseDown={(e) => {
                    e.stopPropagation();
                    handleDragStart(index);
                  }}
                  draggable
                  onDragOver={handleDragOver}
                  onDrop={(e) => {
                    e.stopPropagation();
                    handleDrop(index);
                  }}
                />
              </Col>
              <Col flex="auto">
                <Space>
                  <Tag color="blue">{volume.title}</Tag>
                  <Tag>
                    第{volume.chapter_start}-{volume.chapter_end}章
                  </Tag>
                  <Tag color="green">
                    {volume.chapter_end - volume.chapter_start + 1}章
                  </Tag>
                  {volume.tension_cycle && (
                    <Tag color={
                      volume.tension_cycle === 'rising' ? 'green' :
                      volume.tension_cycle === 'climax' ? 'red' : 'orange'
                    }>
                      {volume.tension_cycle === 'rising' ? '上升' :
                       volume.tension_cycle === 'climax' ? '高潮' : '下降'}
                    </Tag>
                  )}
                </Space>
              </Col>
              <Col>
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteVolume(index);
                  }}
                  disabled={decomposition.volumes.length <= 1}
                />
              </Col>
            </Row>
          ),
          children: (
            <Row gutter={[16, 16]}>
              <Col span={24}>
                <Space orientation="vertical" size="small" style={{ width: '100%' }}>
                  <Typography.Text strong>卷标题</Typography.Text>
                  <Input
                    value={volume.title}
                    onChange={(e) => handleVolumeChange(index, 'title', e.target.value)}
                    placeholder="输入卷标题"
                  />
                </Space>
              </Col>

              <Col span={24}>
                <Space orientation="vertical" size="small" style={{ width: '100%' }}>
                  <Typography.Text strong>卷概要</Typography.Text>
                  <Input.TextArea
                    value={volume.summary}
                    onChange={(e) => handleVolumeChange(index, 'summary', e.target.value)}
                    placeholder="描述本卷的主要内容"
                    rows={3}
                    showCount
                    maxLength={1000}
                  />
                </Space>
              </Col>

              <Col span={8}>
                <Space orientation="vertical" size="small" style={{ width: '100%' }}>
                  <Typography.Text strong>章节数量</Typography.Text>
                  <InputNumber
                    min={MIN_CHAPTERS_PER_VOLUME}
                    max={MAX_CHAPTERS_PER_VOLUME}
                    value={volume.chapter_end - volume.chapter_start + 1}
                    onChange={(val) => handleChapterCountChange(index, val || DEFAULT_CHAPTERS_PER_VOLUME)}
                    style={{ width: '100%' }}
                  />
                  <Slider
                    min={MIN_CHAPTERS_PER_VOLUME}
                    max={MAX_CHAPTERS_PER_VOLUME}
                    value={volume.chapter_end - volume.chapter_start + 1}
                    onChange={(val) => handleChapterCountChange(index, val)}
                  />
                </Space>
              </Col>

              <Col span={8}>
                <Space orientation="vertical" size="small" style={{ width: '100%' }}>
                  <Typography.Text strong>张力循环</Typography.Text>
                  <SelectTensionCycle
                    value={volume.tension_cycle}
                    onChange={(val) => handleVolumeChange(index, 'tension_cycle', val)}
                  />
                </Space>
              </Col>

              <Col span={8}>
                <Space orientation="vertical" size="small" style={{ width: '100%' }}>
                  <Typography.Text strong>主线事件</Typography.Text>
                  <Input
                    value={volume.main_events?.join(', ') || ''}
                    onChange={(e) => handleVolumeChange(
                      index,
                      'main_events',
                      e.target.value.split(',').filter((s) => s.trim())
                    )}
                    placeholder="用逗号分隔多个事件"
                  />
                </Space>
              </Col>

              <Col span={12}>
                <Space orientation="vertical" size="small" style={{ width: '100%' }}>
                  <Typography.Text strong>支线情节</Typography.Text>
                  <Input.TextArea
                    value={volume.side_plots?.join('\n') || ''}
                    onChange={(e) => handleVolumeChange(
                      index,
                      'side_plots',
                      e.target.value.split('\n').filter((s) => s.trim())
                    )}
                    placeholder="每行一个支线情节"
                    rows={2}
                  />
                </Space>
              </Col>

              <Col span={12}>
                <Space orientation="vertical" size="small" style={{ width: '100%' }}>
                  <Typography.Text strong>伏笔分配</Typography.Text>
                  <Input.TextArea
                    value={volume.foreshadowing?.join('\n') || ''}
                    onChange={(e) => handleVolumeChange(
                      index,
                      'foreshadowing',
                      e.target.value.split('\n').filter((s) => s.trim())
                    )}
                    placeholder="每行一个伏笔"
                    rows={2}
                  />
                </Space>
              </Col>
            </Row>
          )
        }))}
      />

      <Divider />

      <Card size="small" type="inner">
        <Space orientation="horizontal" size="middle">
          <SettingOutlined />
          <Typography.Text strong>操作提示</Typography.Text>
        </Space>
        <Typography.Paragraph style={{ marginTop: 8, marginBottom: 0 }}>
          <Typography.Text type="secondary">
            📌 拖拽卷标题左侧的图标可调整卷顺序 | 每卷建议 5-20 章 | 总章节数会根据各卷自动计算
          </Typography.Text>
        </Typography.Paragraph>
      </Card>
    </div>
  );
}



function SelectTensionCycle({ value, onChange }: TensionCycleProps) {
  const options = [
    { value: 'rising', label: '上升', color: 'green' },
    { value: 'climax', label: '高潮', color: 'red' },
    { value: 'falling', label: '下降', color: 'orange' },
    { value: 'flat', label: '平稳', color: 'blue' },
  ];

  return (
    <Space wrap>
      {options.map((opt) => (
        <Tag
          key={opt.value}
          color={opt.color}
          style={{
            cursor: 'pointer',
            opacity: value === opt.value ? 1 : 0.5,
          }}
          onClick={() => onChange?.(opt.value)}
        >
          {opt.label}
        </Tag>
      ))}
    </Space>
  );
}
