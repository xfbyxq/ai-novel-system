import { create } from 'zustand';
import type { GenerationTask } from '@/api/types';
import { getGenerationTasks, getGenerationTask } from '@/api/generation';

interface GenerationStore {
  tasks: GenerationTask[];
  loading: boolean;
  fetchTasks: (novelId: string) => Promise<void>;
  refreshTask: (taskId: string) => Promise<GenerationTask | null>;
}

export const useGenerationStore = create<GenerationStore>((set, get) => ({
  tasks: [],
  loading: false,

  fetchTasks: async (novelId: string) => {
    set({ loading: true });
    try {
      const res = await getGenerationTasks(novelId, undefined, 1, 100);
      set({ tasks: res.items });
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
}));
