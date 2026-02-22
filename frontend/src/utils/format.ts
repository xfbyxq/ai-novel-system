import dayjs from 'dayjs';

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '-';
  return dayjs(dateStr).format('YYYY-MM-DD HH:mm');
}

export function formatNumber(num: number | null | undefined): string {
  if (num == null) return '0';
  return num.toLocaleString('zh-CN');
}

export function formatCost(cost: number | null | undefined): string {
  if (cost == null) return '¥0.0000';
  return `¥${Number(cost).toFixed(4)}`;
}

export function formatWordCount(count: number | null | undefined): string {
  if (!count) return '0';
  if (count >= 10000) return `${(count / 10000).toFixed(1)}万`;
  return count.toLocaleString('zh-CN');
}
