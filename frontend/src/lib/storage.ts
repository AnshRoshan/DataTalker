import type { ActiveDbRef, ChatMessageData } from '../types';

export const CHAT_HISTORY_KEY = 'datatalker.chatHistory';
export const ACTIVE_DB_REF_KEY = 'datatalker.activeDbRef';
export const API_URL_KEY = 'apiUrl';
export const API_KEY_KEY = 'apiKey';
export const LLM_PROVIDER_KEY = 'llmProvider';
export const LLM_KEY = 'llmApiKey';

/** Cap on how many messages are persisted to localStorage (most recent are kept). */
export const MAX_PERSISTED_MESSAGES = 50;

/** Persisted messages must be JSON-safe; results may contain anything the DB returned. */
type PersistedMessage = Omit<ChatMessageData, 'results'> & {
  results: unknown;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

function readJson(key: string): unknown {
  try {
    const raw = localStorage.getItem(key);
    return raw === null ? null : JSON.parse(raw);
  } catch {
    return null;
  }
}

function writeJson(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Best-effort persistence.
  }
}

export function loadChatHistory(): ChatMessageData[] {
  const parsed = readJson(CHAT_HISTORY_KEY);
  if (!Array.isArray(parsed)) return [];
  return parsed
    .filter(
      (m): m is PersistedMessage =>
        isRecord(m) && typeof m.id === 'string' && typeof m.question === 'string',
    )
    .map(m => ({
      id: m.id,
      question: m.question,
      answer: typeof m.answer === 'string' ? m.answer : '',
      sql: typeof m.sql === 'string' ? m.sql : '',
      results: (isRecord(m.results) || Array.isArray(m.results)
        ? m.results
        : []) as ChatMessageData['results'],
      // A restored message can never still be "typing".
      isTyping: false,
      follow_up_questions: Array.isArray(m.follow_up_questions)
        ? (m.follow_up_questions as string[])
        : undefined,
      results_truncated:
        typeof m.results_truncated === 'boolean' ? m.results_truncated : undefined,
      sql_executed: typeof m.sql_executed === 'string' ? m.sql_executed : undefined,
      latency_ms: typeof m.latency_ms === 'number' ? m.latency_ms : undefined,
      row_cap: typeof m.row_cap === 'number' ? m.row_cap : undefined,
    }));
}

export function saveChatHistory(messages: ChatMessageData[]): void {
  const capped = messages.slice(-MAX_PERSISTED_MESSAGES).map(m => ({
    ...m,
    isTyping: false,
  }));
  // Shrink-and-retry so a large single message can't silently lose the whole history.
  let candidate = capped;
  while (candidate.length > 0) {
    try {
      localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(candidate));
      return;
    } catch {
      candidate = candidate.slice(Math.ceil(candidate.length / 2));
    }
  }
  try {
    localStorage.removeItem(CHAT_HISTORY_KEY);
  } catch {
    // Nothing more we can do; persistence is best-effort.
  }
}

/**
 * Persist the active DB reference. `file` refs are session-only (a File object
 * cannot be serialized), so they are dropped on save and restored as null.
 */
export function loadActiveDbRef(): ActiveDbRef | null {
  const parsed = readJson(ACTIVE_DB_REF_KEY);
  if (!isRecord(parsed)) return null;
  if (parsed.kind === 'connection' && typeof parsed.id === 'number' && typeof parsed.name === 'string') {
    return { kind: 'connection', id: parsed.id, name: parsed.name };
  }
  if (parsed.kind === 'path' && typeof parsed.path === 'string' && parsed.path) {
    return { kind: 'path', path: parsed.path };
  }
  if (parsed.kind === 'string' && typeof parsed.connectionString === 'string' && parsed.connectionString) {
    return { kind: 'string', connectionString: parsed.connectionString };
  }
  return null;
}

export function saveActiveDbRef(ref: ActiveDbRef | null): void {
  if (!ref) {
    try {
      localStorage.removeItem(ACTIVE_DB_REF_KEY);
    } catch {
      // Best-effort.
    }
    return;
  }
  switch (ref.kind) {
    case 'connection':
      writeJson(ACTIVE_DB_REF_KEY, ref);
      break;
    case 'path':
      writeJson(ACTIVE_DB_REF_KEY, ref);
      break;
    case 'string':
      writeJson(ACTIVE_DB_REF_KEY, ref);
      break;
    case 'file':
      writeJson(ACTIVE_DB_REF_KEY, { kind: 'file' }); // session-only marker
      break;
  }
}

// The API serves this bundle, so a deployed instance is same-origin and needs no
// configuration. Vite's dev server is the one place the API lives on another port.
const FALLBACK_URL = 'http://127.0.0.1:8000';

function defaultApiUrl(): string {
  try {
    const { protocol, host, port } = window.location;
    if (!protocol.startsWith('http') || port === '5173') return FALLBACK_URL;
    return `${protocol}//${host}`;
  } catch {
    return FALLBACK_URL;
  }
}

const DEFAULT_URL = defaultApiUrl();

export function loadApiUrl(): string {
  try {
    return localStorage.getItem(API_URL_KEY) || DEFAULT_URL;
  } catch {
    return DEFAULT_URL;
  }
}

/** Bring-your-own LLM key. Kept in the browser and sent as X-LLM-* headers on each
 * request — the server holds it for the duration of that request only. */
export interface LlmCredentials {
  provider: string;
  apiKey: string;
}

export function loadLlmCredentials(): LlmCredentials {
  try {
    return {
      provider: localStorage.getItem(LLM_PROVIDER_KEY) || '',
      apiKey: localStorage.getItem(LLM_KEY) || '',
    };
  } catch {
    return { provider: '', apiKey: '' };
  }
}

export function saveLlmCredentials(creds: LlmCredentials): void {
  try {
    localStorage.setItem(LLM_PROVIDER_KEY, creds.provider);
    localStorage.setItem(LLM_KEY, creds.apiKey);
  } catch {
    /* private-mode browsers: the key simply won't persist */
  }
}

export function loadApiKey(): string {
  try {
    return localStorage.getItem(API_KEY_KEY) || '';
  } catch {
    return '';
  }
}

export function saveSettings(apiUrl: string, apiKey: string): void {
  try {
    localStorage.setItem(API_URL_KEY, apiUrl);
    localStorage.setItem(API_KEY_KEY, apiKey);
  } catch {
    // Best-effort.
  }
}
