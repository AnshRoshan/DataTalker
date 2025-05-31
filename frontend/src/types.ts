export interface ChatMessageData {
    id: number;
    question: string;
    answer: string;
    sql: string;
    results: Record<string, any>[] | Record<string, any>;
    isTyping: boolean;
    follow_up_questions?: string[];
}

export type InputMethod = "upload" | "url";