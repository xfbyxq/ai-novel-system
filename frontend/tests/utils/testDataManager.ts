import { API } from '../../src/api/client';

// 测试数据管理类
class TestDataManager {
  private api: API;
  private createdResources: string[] = [];

  constructor() {
    this.api = new API();
  }

  // 生成测试小说数据
  async createTestNovel() {
    const novelData = {
      title: `测试小说_${Date.now()}`,
      description: '这是一个测试小说',
      genre: '玄幻',
      author: '测试作者',
      status: '连载中',
      word_count: 10000,
    };

    try {
      const response = await this.api.createNovel(novelData);
      const novelId = response.id;
      this.createdResources.push(`novel_${novelId}`);
      return response;
    } catch (error) {
      console.error('创建测试小说失败:', error);
      throw error;
    }
  }

  // 生成测试章节数据
  async createTestChapter(novelId: string) {
    const chapterData = {
      novel_id: novelId,
      title: `测试章节_${Date.now()}`,
      content: '这是测试章节内容',
      chapter_number: 1,
    };

    try {
      const response = await this.api.createChapter(chapterData);
      const chapterId = response.id;
      this.createdResources.push(`chapter_${chapterId}`);
      return response;
    } catch (error) {
      console.error('创建测试章节失败:', error);
      throw error;
    }
  }

  // 清理测试数据
  async cleanup() {
    console.log('开始清理测试数据...');

    for (const resource of this.createdResources) {
      try {
        if (resource.startsWith('novel_')) {
          const novelId = resource.replace('novel_', '');
          await this.api.deleteNovel(novelId);
        } else if (resource.startsWith('chapter_')) {
          const chapterId = resource.replace('chapter_', '');
          await this.api.deleteChapter(chapterId);
        }
        console.log(`清理资源成功: ${resource}`);
      } catch (error) {
        console.error(`清理资源失败 ${resource}:`, error);
      }
    }

    this.createdResources = [];
    console.log('测试数据清理完成');
  }

  // 获取所有创建的资源
  getCreatedResources() {
    return [...this.createdResources];
  }
}

// 导出单例实例
export const testDataManager = new TestDataManager();
