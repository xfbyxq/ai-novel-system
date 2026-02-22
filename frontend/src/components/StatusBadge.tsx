import { Tag } from 'antd';
import { NOVEL_STATUS_MAP, CHAPTER_STATUS_MAP, TASK_STATUS_MAP } from '@/utils/constants';

type MapType = 'novel' | 'chapter' | 'task';

const maps: Record<MapType, Record<string, { label: string; color: string }>> = {
  novel: NOVEL_STATUS_MAP,
  chapter: CHAPTER_STATUS_MAP,
  task: TASK_STATUS_MAP,
};

interface Props {
  type: MapType;
  status: string;
}

export default function StatusBadge({ type, status }: Props) {
  const item = maps[type]?.[status];
  if (!item) return <Tag>{status}</Tag>;
  return <Tag color={item.color}>{item.label}</Tag>;
}
