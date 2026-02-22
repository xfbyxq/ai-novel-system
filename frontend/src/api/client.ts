import axios from 'axios';
import { message } from 'antd';

const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 300000,  // 5分钟超时，用于长时间 AI 生成任务
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const msg =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      '请求失败';
    message.error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    return Promise.reject(error);
  },
);

export default apiClient;
