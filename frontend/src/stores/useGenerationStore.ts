import { create } from 'zustand';
import type { GenerationTask } from '@/api/types';
import { getGenerationTasks, getGenerationTask } from '@/api/generation';

interface GenerationStore {
  tasks: GenerationTask[];
  loading: boolean;
  // 大纲完善任务特定状态
  currentEnhancementTask: {
    taskId: string | null;
    status: 'idle' | 'pending' | 'running' | 'completed' | 'failed';
    createdAt: Date | null;
  } | null;
  fetchTasks: (novelId: string) => Promise<void>;
  refreshTask: (taskId: string) => Promise<GenerationTask | null>;
  // 大纲完善任务管理
  setCurrentEnhancementTask: (task: { taskId: string; status: string; createdAt: Date } | null) => void;
  clearCurrentEnhancementTask: () => void;
  hasRunningEnhancementTask: () => boolean;
}

export const useGenerationStore = create<GenerationStore>((set, get) => ({
  tasks: [],
  loading: false,
  currentEnhancementTask: null,

  fetchTasks: async (novelId: string) => {
    set({ loading: true });
    try {
      const res = await getGenerationTasks(novelId, undefined, 1, 100);
      set({ tasks: res.items });
    } catch (error) {
      console.error('Failed to fetch generation tasks:', error);
      set({ tasks: [] });
    } finally {
      set({ loading: false });
    }
  },

  refreshTask: async (taskId: string) => {
    try {
      const task = await getGenerationTask(taskId);
      set({
        tasks: get().tasks.map((t) => (t.id === taskId ? task : t)),
      });
      return task;
    } catch {
      return null;
    }
  },

  setCurrentEnhancementTask: (task) => {
    set({ 
      currentEnhancementTask: task 
        ? { 
            taskId: task.taskId, 
            status: task.status as any, 
            createdAt: task.createdAt 
          } 
        : null 
    });
  },

  clearCurrentEnhancementTask: () => {
    set({ currentEnhancementTask: null });
  },

  hasRunningEnhancementTask: () => {
    const currentTask = get().currentEnhancementTask;
    return !!(currentTask && (currentTask.status === 'pending' || currentTask.status === 'running'));
  }
}));
