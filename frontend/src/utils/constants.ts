export const NOVEL_STATUS_MAP: Record<string, { label: string; color: string }> = {
  planning: { label: '企划中', color: 'blue' },
  writing: { label: '写作中', color: 'orange' },
  completed: { label: '已完成', color: 'green' },
  published: { label: '已发布', color: 'purple' },
};

export const CHAPTER_STATUS_MAP: Record<string, { label: string; color: string }> = {
  draft: { label: '草稿', color: 'default' },
  reviewing: { label: '审核中', color: 'processing' },
  published: { label: '已发布', color: 'success' },
};

export const TASK_STATUS_MAP: Record<string, { label: string; color: string }> = {
  pending: { label: '等待中', color: 'default' },
  running: { label: '运行中', color: 'processing' },
  completed: { label: '已完成', color: 'success' },
  failed: { label: '失败', color: 'error' },
  cancelled: { label: '已取消', color: 'warning' },
};

export const ROLE_TYPE_MAP: Record<string, { label: string; color: string }> = {
  protagonist: { label: '主角', color: '#faad14' },
  supporting: { label: '配角', color: '#1890ff' },
  antagonist: { label: '反派', color: '#f5222d' },
  minor: { label: '路人', color: '#999' },
};

export const GENDER_MAP: Record<string, string> = {
  male: '男',
  female: '女',
  other: '其他',
};

export const GENRE_OPTIONS = [
  '玄幻', '奇幻', '武侠', '仙侠', '都市', '现实', '军事', '历史',
  '游戏', '体育', '科幻', '悬疑', '轻小说',
];
