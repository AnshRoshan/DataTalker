import axios from 'axios';
import type {
  ActiveDbRef,
  ChatResponse,
  Connection,
  ConnectionCheckResponse,
  ConnectionsResponse,
  HealthStatus,
  NewConnectionInput,
  SchemaGraphResponse,
} from '../types';

export const DEFAULT_API_URL = 'http://127.0.0.1:8000';
export const REQUEST_TIMEOUT_MS = 120_000;

/** How many previous turns are sent to the backend for context. */
export const HISTORY_WINDOW = 5;

export function authHeaders(apiKey: string): Record<string, string> {
  return apiKey ? { Authorization: `Bearer ${apiKey}` } : {};
}

/** Extract a human-readable message from any backend/frontend error. */
export function getErrorMessage(err: unknown, timedOut = false): string {
  if (axios.isCancel(err)) {
    return timedOut
      ? 'The request timed out after 120 seconds. Try a simpler question or check the backend.'
      : 'Request cancelled.';
  }
  if (axios.isAxiosError(err)) {
    const data: unknown = err.response?.data;
    if (data && typeof data === 'object') {
      const detail = (data as { detail?: unknown }).detail;
      const errorText = (data as { error?: unknown }).error;
      const message = detail ?? errorText;
      if (typeof message === 'string' && message) return message;
      if (message !== undefined && message !== null) return JSON.stringify(message);
    }
    if (typeof data === 'string' && data) return data;
    if (err.response) return `Server error (HTTP ${err.response.status}).`;
    return 'Failed to reach the server. Check if the backend is running.';
  }
  if (err instanceof Error && err.message) return err.message;
  return 'An unexpected error occurred.';
}

/** Append the active DB reference fields to a multipart form. */
export function appendDbRef(formData: FormData, ref: ActiveDbRef | null): void {
  if (!ref) return;
  if (ref.kind === 'connection') {
    formData.append('connection_id', String(ref.id));
  } else if (ref.kind === 'file') {
    formData.append('db_file', ref.file);
  } else if (ref.kind === 'path') {
    formData.append('db_path', ref.path);
  } else if (ref.kind === 'string') {
    const s = ref.connectionString;
    if (/^https?:\/\//i.test(s)) {
      formData.append('db_url', s);
    } else {
      formData.append('db_connection_string', s);
    }
  }
}

export async function sendChat(opts: {
  apiUrl: string;
  apiKey: string;
  question: string;
  dbRef: ActiveDbRef | null;
  history: { question: string; answer: string; sql: string }[];
  signal: AbortSignal;
}): Promise<ChatResponse> {
  const formData = new FormData();
  formData.append('question', opts.question);
  appendDbRef(formData, opts.dbRef);
  if (opts.history.length > 0) {
    formData.append('history', JSON.stringify(opts.history));
  }
  const response = await axios.post<ChatResponse>(`${opts.apiUrl}/chat/`, formData, {
    headers: authHeaders(opts.apiKey),
    signal: opts.signal, // the caller enforces the 120s ceiling via AbortController
  });
  return response.data;
}

export async function fetchHealth(apiUrl: string, apiKey: string): Promise<HealthStatus> {
  try {
    // /health requires no auth; send it anyway so the URL/key combo is validated.
    const res = await axios.get(`${apiUrl}/health`, {
      headers: authHeaders(apiKey),
      timeout: 8_000,
    });
    return res.status === 200 ? 'connected' : 'disconnected';
  } catch {
    return 'disconnected';
  }
}

export async function fetchConnections(apiUrl: string, apiKey: string): Promise<ConnectionsResponse> {
  const res = await axios.get<ConnectionsResponse>(`${apiUrl}/connections/`, {
    headers: authHeaders(apiKey),
    timeout: 20_000,
  });
  return res.data;
}

export async function createConnection(
  apiUrl: string,
  apiKey: string,
  input: NewConnectionInput,
): Promise<Connection> {
  const res = await axios.post<Connection>(`${apiUrl}/connections/`, input, {
    headers: authHeaders(apiKey),
    timeout: 60_000,
  });
  return res.data;
}

export async function deleteConnection(
  apiUrl: string,
  apiKey: string,
  id: number,
): Promise<void> {
  await axios.delete(`${apiUrl}/connections/${id}`, {
    headers: authHeaders(apiKey),
    timeout: 20_000,
  });
}

export async function checkConnection(
  apiUrl: string,
  apiKey: string,
  id: number,
): Promise<ConnectionCheckResponse> {
  const res = await axios.post<ConnectionCheckResponse>(
    `${apiUrl}/connections/${id}/check`,
    null,
    { headers: authHeaders(apiKey), timeout: 60_000 },
  );
  return res.data;
}

export async function fetchSchemaGraph(opts: {
  apiUrl: string;
  apiKey: string;
  dbRef: ActiveDbRef | null;
  signal?: AbortSignal;
}): Promise<SchemaGraphResponse> {
  const formData = new FormData();
  appendDbRef(formData, opts.dbRef);
  const res = await axios.post<SchemaGraphResponse>(`${opts.apiUrl}/schema/graph/`, formData, {
    headers: authHeaders(opts.apiKey),
    signal: opts.signal,
    timeout: 120_000,
  });
  return res.data;
}
