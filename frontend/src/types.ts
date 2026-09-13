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

export type InputMethod = "upload" | "url";

/** Shape of the POST /chat/ response (all fields optional; only grows). */
export interface ChatResponse {
    answer?: string;
    sql?: string;
    results?: Record<string, unknown>[] | Record<string, unknown>;
    follow_up_questions?: string[];
    results_truncated?: boolean;
    sql_executed?: string;
    latency_ms?: number;
    row_cap?: number;
}

/** One previous turn sent to the backend in the optional `history` form field. */
export interface HistoryTurn {
    question: string;
    answer: string;
    sql: string;
}

export type HealthStatus = "checking" | "connected" | "disconnected";
