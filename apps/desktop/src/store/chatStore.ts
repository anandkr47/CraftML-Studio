/**
 * Chat Store
 * Sessions, active conversation, generation settings and streaming state.
 */

import { create } from 'zustand';
import {
  chatApi,
  ChatMessage,
  ChatSession,
  DEFAULT_SETTINGS,
  GenerationSettings,
  LocalModel,
  streamReply,
} from '../api/chat';
import { errorText } from '../api/errors';

interface ChatState {
  sessions: ChatSession[];
  models: LocalModel[];
  activeId: string | null;
  messages: ChatMessage[];
  modelId: string | null;
  systemPrompt: string;
  useKb: boolean;
  settings: GenerationSettings;
  streaming: boolean;
  error: string | null;
  abort: AbortController | null;

  init: () => Promise<void>;
  refreshModels: () => Promise<void>;
  selectSession: (id: string) => Promise<void>;
  newSession: () => Promise<void>;
  deleteSession: (id: string) => Promise<void>;
  setModel: (id: string | null) => Promise<void>;
  setSystemPrompt: (prompt: string) => void;
  setUseKb: (on: boolean) => void;
  setSettings: (patch: Partial<GenerationSettings>) => void;
  send: (content: string) => Promise<void>;
  stop: () => void;
}

export const useChatStore = create<ChatState>((set, get) => {
  const applySession = (s: ChatSession) =>
    set({
      activeId: s.id,
      messages: s.messages ?? [],
      modelId: s.model_id,
      systemPrompt: s.system_prompt,
      useKb: s.use_kb,
      settings: s.params,
      error: null,
    });

  const refreshSessions = async () => set({ sessions: await chatApi.listSessions() });

  return {
    sessions: [],
    models: [],
    activeId: null,
    messages: [],
    modelId: null,
    systemPrompt: '',
    useKb: false,
    settings: DEFAULT_SETTINGS,
    streaming: false,
    error: null,
    abort: null,

    init: async () => {
      try {
        await Promise.all([refreshSessions(), get().refreshModels()]);
        const { sessions, activeId } = get();
        if (!activeId && sessions.length) await get().selectSession(sessions[0].id);
      } catch (e) {
        set({ error: `Couldn't load chats: ${errorText(e)}` });
      }
    },

    refreshModels: async () => {
      try {
        set({ models: await chatApi.listModels() });
      } catch (e) {
        set({ error: `Couldn't list models: ${errorText(e)}` });
      }
    },

    selectSession: async (id) => {
      if (get().streaming) return;
      try {
        applySession(await chatApi.getSession(id));
      } catch (e) {
        set({ error: errorText(e) });
      }
    },

    newSession: async () => {
      if (get().streaming) return;
      const { modelId, systemPrompt, settings, useKb } = get();
      try {
        const created = await chatApi.createSession({
          model_id: modelId,
          system_prompt: systemPrompt,
          params: settings,
          use_kb: useKb,
        });
        applySession({ ...created, messages: [] });
        await refreshSessions();
      } catch (e) {
        set({ error: `Couldn't create a chat: ${errorText(e)}` });
      }
    },

    deleteSession: async (id) => {
      try {
        await chatApi.deleteSession(id);
        await refreshSessions();
      } catch (e) {
        set({ error: errorText(e) });
        return;
      }
      if (get().activeId === id) {
        const next = get().sessions[0];
        if (next) await get().selectSession(next.id);
        else set({ activeId: null, messages: [] });
      }
    },

    setModel: async (id) => {
      set({ modelId: id });
      const { activeId } = get();
      if (activeId && id) {
        await chatApi.updateSession(activeId, { model_id: id }).catch((e) => set({ error: errorText(e) }));
      }
    },

    setSystemPrompt: (systemPrompt) => set({ systemPrompt }),
    setUseKb: (useKb) => set({ useKb }),
    setSettings: (patch) => set((s) => ({ settings: { ...s.settings, ...patch } })),

    send: async (content) => {
      const state = get();
      if (state.streaming || !content.trim()) return;
      if (!state.modelId) {
        set({ error: 'Select a model first' });
        return;
      }
      if (!state.activeId) await get().newSession();
      const sessionId = get().activeId;
      if (!sessionId) return; // creating the chat failed; the error is already shown
      const abort = new AbortController();
      const draft: ChatMessage = { id: `draft-${Date.now()}`, role: 'assistant', content: '', sources: [] };
      set((s) => ({
        streaming: true,
        error: null,
        abort,
        messages: [
          ...s.messages,
          { id: `user-${Date.now()}`, role: 'user', content, sources: [] },
          draft,
        ],
      }));

      const patchDraft = (fn: (m: ChatMessage) => ChatMessage) =>
        set((s) => ({ messages: s.messages.map((m) => (m.id === draft.id ? fn(m) : m)) }));

      try {
        await streamReply(
          sessionId,
          {
            content,
            model_id: get().modelId,
            system_prompt: get().systemPrompt,
            params: get().settings,
            use_kb: get().useKb,
          },
          {
            onDelta: (text) => patchDraft((m) => ({ ...m, content: m.content + text })),
            onDone: (info) => patchDraft((m) => ({ ...m, id: info.message_id, sources: info.sources })),
          },
          abort.signal
        );
      } catch (e) {
        if ((e as Error).name !== 'AbortError') {
          set({ error: errorText(e) });
          // Drop an empty assistant bubble when generation failed before any output.
          set((s) => ({ messages: s.messages.filter((m) => m.id !== draft.id || m.content) }));
        }
      } finally {
        set({ streaming: false, abort: null });
        await Promise.all([refreshSessions(), get().refreshModels()]);
      }
    },

    stop: () => get().abort?.abort(),
  };
});
