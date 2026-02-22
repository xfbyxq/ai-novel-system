import { Card, Statistic } from 'antd';
import type { ReactNode } from 'react';

interface Props {
  title: string;
  value: string | number;
  icon: ReactNode;
  color?: string;
}

export default function StatsCard({ title, value, icon, color }: Props) {
  return (
    <Card>
      <Statistic
        title={title}
        value={value}
        prefix={<span style={{ color: color || '#1890ff' }}>{icon}</span>}
      />
    </Card>
  );
}
