import axios from 'axios';
import { message } from 'antd';

const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 300000,  // 5分钟超时，用于长时间 AI 生成任务
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.request.use(
  (config) => {
    console.log('📡 API 请求:', config.method?.toUpperCase(), config.url, config.data);
    return config;
  },
  (error) => {
    console.error('📡 请求拦截器错误:', error);
    return Promise.reject(error);
  }
);

apiClient.interceptors.response.use(
  (response) => {
    console.log('📥 API 响应:', response.status, response.config.url);
    return response;
  },
  (error) => {
    console.error('📥 响应错误:', error.response?.status, error.response?.config?.url, error.response?.data);
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
