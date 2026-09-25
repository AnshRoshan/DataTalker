/* ------------------------------------------------------------------ */
/* Chat contract (POST /chat/)                                         */
/* ------------------------------------------------------------------ */

/** Shape of the POST /chat/ response (all fields optional; only grows). */
export interface ChatResponse {
  answer?: string;
  sql?: string;
  results?: Record<string, unknown>[] | Record<string, unknown>;
  follow_up_questions?: string[];
  results_truncated?: boolean;
  sql_executed?: string;
  validator_rejected?: boolean;
  latency_ms?: number;
  row_cap?: number;
}

/** One previous turn sent to the backend in the optional `history` form field. */
export interface HistoryTurn {
  question: string;
  answer: string;
  sql: string;
}

/** A single conversation turn as held/persisted by the UI. */
export interface ChatMessageData {
  id: string;
  question: string;
  answer: string;
  sql: string;
  results: Record<string, unknown>[] | Record<string, unknown>;
  isTyping: boolean;
  follow_up_questions?: string[];
  results_truncated?: boolean;
  sql_executed?: string;
  latency_ms?: number;
  row_cap?: number;
}

/* ------------------------------------------------------------------ */
/* Connections contract (/connections/)                                */
/* ------------------------------------------------------------------ */

export interface ConnectionStatusOk {
  ok: true;
  dialect?: string;
  driver?: string;
  server_version?: string;
  table_count?: number;
  sample_tables?: string[];
  warnings?: string[];
}

export interface ConnectionStatusError {
  ok: false;
  error: string;
}

export type ConnectionLastStatus = ConnectionStatusOk | ConnectionStatusError;

export interface Connection {
  id: number;
  name: string;
  notes?: string | null;
  connection_string_masked: string;
  created_at?: string;
  last_checked_at?: string | null;
  last_status?: ConnectionLastStatus | null;
  /** Convenience fields the server lifts out of the last successful check. */
  dialect?: string | null;
  table_count?: number | null;
}

export interface ConnectionsResponse {
  connections: Connection[];
  total: number;
}

export interface NewConnectionInput {
  name: string;
  connection_string: string;
  notes?: string;
}

export interface ConnectionCheckResponse {
  id: number;
  last_checked_at?: string;
  last_status?: ConnectionLastStatus;
}

/* ------------------------------------------------------------------ */
/* Schema contract (/schema/graph/, /schema/)                          */
/* ------------------------------------------------------------------ */

export interface GraphColumn {
  name: string;
  type?: string;
  primary_key?: boolean;
  foreign_keys?: { column?: string; references_table?: string; references_column?: string }[];
}

export interface GraphNode {
  id: string | number;
  name: string;
  columns: GraphColumn[];
}

export interface GraphEdge {
  source: string | number;
  target: string | number;
  label?: string;
  inferred?: boolean;
}

export interface SchemaGraphResponse {
  dialect: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  table_count: number;
  truncated?: boolean;
}

export interface SchemaTable {
  name: string;
  columns?: { name: string; type?: string; primary_key?: boolean; foreign_keys?: unknown[] }[];
  row_count?: number | null;
  [key: string]: unknown;
}

export interface SchemaResponse {
  message?: string;
  database_dialect?: string;
  tables?: SchemaTable[];
  schema_description?: string;
  cached?: boolean;
}

/* ------------------------------------------------------------------ */
/* Active DB reference                                                 */
/* ------------------------------------------------------------------ */

/**
 * The database the user is currently talking to. Sent on /chat/ and
 * /schema/graph/ as either `connection_id` (preferred) or one of the
 * direct reference fields. `file` refs are session-only (File objects
 * cannot be persisted); every other kind is restored from localStorage.
 */
export type ActiveDbRef =
  | { kind: 'connection'; id: number; name: string }
  | { kind: 'file'; file: File; name: string }
  | { kind: 'path'; path: string }
  | { kind: 'string'; connectionString: string };

export type HealthStatus = 'checking' | 'connected' | 'disconnected';

export type ViewId = 'chat' | 'connections' | 'schema';
