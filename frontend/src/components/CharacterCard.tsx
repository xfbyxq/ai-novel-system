import { Card, Tag, Typography, Space } from 'antd';
import type { Character } from '@/api/types';
import { ROLE_TYPE_MAP, GENDER_MAP } from '@/utils/constants';

interface Props {
  character: Character;
  onClick?: () => void;
}

export default function CharacterCard({ character, onClick }: Props) {
  const role = ROLE_TYPE_MAP[character.role_type || 'minor'];

  return (
    <Card hoverable size="small" onClick={onClick}>
      <Space orientation="vertical" size={2} style={{ width: '100%' }}>
        <Space>
          <Typography.Text strong>{character.name}</Typography.Text>
          <Tag color={role.color}>{role.label}</Tag>
          {character.gender && (
            <Typography.Text type="secondary">
              {GENDER_MAP[character.gender] || character.gender}
            </Typography.Text>
          )}
          {character.age && (
            <Typography.Text type="secondary">{character.age}岁</Typography.Text>
          )}
        </Space>
        {character.personality && (
          <Typography.Paragraph
            type="secondary"
            ellipsis={{ rows: 2 }}
            style={{ margin: 0, fontSize: 12 }}
          >
            {character.personality}
          </Typography.Paragraph>
        )}
      </Space>
    </Card>
  );
}
