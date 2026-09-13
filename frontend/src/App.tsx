import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import type { ChatMessageData, ChatResponse, HistoryTurn, InputMethod } from './types';
import {
    API_KEY_KEY,
    API_URL_KEY,
    loadChatHistory,
    loadDbRef,
    saveChatHistory,
    saveDbRef,
} from './lib/storage';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import ChatArea from './components/ChatArea';
import InputArea from './components/InputArea';

const REQUEST_TIMEOUT_MS = 120_000;
/** How many previous turns are sent to the backend for context. */
const HISTORY_WINDOW = 5;
const DEFAULT_API_URL = 'http://127.0.0.1:8000';

const getErrorMessage = (err: unknown, timedOut: boolean): string => {
    if (axios.isCancel(err)) {
        return timedOut
            ? 'The request timed out after 120 seconds. Try a simpler question or check the backend.'
            : 'Request cancelled.';
    }
    if (axios.isAxiosError(err)) {
        const data: unknown = err.response?.data;
        if (data && typeof data === 'object') {
            const detail = (data as { detail?: unknown; error?: unknown }).detail;
            const errorText = (data as { error?: unknown }).error;
            const message = detail ?? errorText;
            if (typeof message === 'string' && message) return message;
            if (message !== undefined && message !== null) return JSON.stringify(message);
        }
        if (typeof data === 'string' && data) return data;
        if (err.response) return `Server error (HTTP ${err.response.status}).`;
        return 'Failed to reach the server. Check if the backend is running.';
    }
    return 'An unexpected error occurred.';
};

const App: React.FC = () => {
    const [chatHistory, setChatHistory] = useState<ChatMessageData[]>(() => loadChatHistory());
    const [inputMethod, setInputMethod] = useState<InputMethod>(() => loadDbRef()?.inputMethod ?? 'upload');
    const [dbPath, setDbPath] = useState<string>(() => loadDbRef()?.dbPath ?? '');
    const [dbUrl, setDbUrl] = useState<string>(() => loadDbRef()?.dbUrl ?? '');
    const [dbFile, setDbFile] = useState<File | null>(null);
    const [userInput, setUserInput] = useState<string>('');
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [sidebarOpen, setSidebarOpen] = useState<boolean>(true);
    const [apiUrl, setApiUrl] = useState<string>(() => localStorage.getItem(API_URL_KEY) || DEFAULT_API_URL);
    const [apiKey, setApiKey] = useState<string>(() => localStorage.getItem(API_KEY_KEY) || '');
    const abortControllerRef = useRef<AbortController | null>(null);

    useEffect(() => {
        const mediaQuery = window.matchMedia('(max-width: 768px)');
        const handleMediaQueryChange = (e: MediaQueryListEvent) => {
            setSidebarOpen(!e.matches);
        };
        if (mediaQuery.matches) {
            setSidebarOpen(false);
        }

        mediaQuery.addEventListener('change', handleMediaQueryChange);
        return () => mediaQuery.removeEventListener('change', handleMediaQueryChange);
    }, []);

    // Persistence (FE-09)
    useEffect(() => {
        saveChatHistory(chatHistory);
    }, [chatHistory]);
    useEffect(() => {
        saveDbRef({ inputMethod, dbPath, dbUrl });
    }, [inputMethod, dbPath, dbUrl]);

    const isAbsolutePath = (path: string): boolean => {
        // Check for Windows absolute paths (C:\, D:\, etc.)
        if (/^[A-Za-z]:\\/.test(path)) return true;
        // Check for Unix/Linux absolute paths (starting with /)
        if (path.startsWith('/')) return true;
        // Check for UNC paths (\\server\share)
        if (path.startsWith('\\\\')) return true;
        return false;
    };

    const isPostgresUrl = (url: string): boolean => {
        return url.startsWith('postgresql://') || url.startsWith('postgres://');
    };

    const validateDbSelection = (): string | null => {
        if (inputMethod === 'upload' && !dbFile && !dbPath.trim()) {
            return 'Please select a local database file (or provide an advanced server path) first.';
        }
        if (inputMethod === 'upload' && dbPath.trim() && !isAbsolutePath(dbPath)) {
            return 'Database path must be absolute (e.g., C:\\path\\to\\file.db or /path/to/file.db).';
        }
        if (inputMethod === 'url' && !dbUrl.trim()) {
            return 'Please provide a database URL first.';
        }
        return null;
    };

    /**
     * Single request path for both new questions and follow-up clicks (FE-05).
     * Returns true when the question was accepted and dispatched.
     */
    const sendQuestion = async (question: string, isFollowUp: boolean): Promise<boolean> => {
        const trimmedQuestion = question.trim();
        if (!trimmedQuestion) return false;

        const validationError = validateDbSelection();
        if (validationError) {
            setError(validationError);
            return false;
        }

        setIsLoading(true);
        setError(null);
        if (!isFollowUp) {
            setUserInput('');
        }

        const newChat: ChatMessageData = {
            id: crypto.randomUUID(),
            question: trimmedQuestion,
            answer: '',
            sql: '',
            results: [],
            isTyping: true,
        };

        setChatHistory(prev => [...prev, newChat]);

        const controller = new AbortController();
        abortControllerRef.current = controller;
        let timedOut = false;
        const timeoutId = window.setTimeout(() => {
            timedOut = true;
            controller.abort();
        }, REQUEST_TIMEOUT_MS);

        try {
            const formData = new FormData();
            formData.append('question', trimmedQuestion);

            if (inputMethod === 'upload') {
                if (dbFile) {
                    formData.append('db_file', dbFile);
                } else if (dbPath) {
                    formData.append('db_path', dbPath);
                }
            } else if (dbUrl) {
                if (isPostgresUrl(dbUrl)) {
                    formData.append('db_connection_string', dbUrl);
                } else {
                    formData.append('db_url', dbUrl);
                }
            }

            // Send the last few completed turns so the backend can use conversation context.
            const historyTurns: HistoryTurn[] = chatHistory
                .filter(chat => !chat.isTyping)
                .slice(-HISTORY_WINDOW)
                .map(chat => ({ question: chat.question, answer: chat.answer, sql: chat.sql }));
            if (historyTurns.length > 0) {
                formData.append('history', JSON.stringify(historyTurns));
            }

            const headers: Record<string, string> = {};
            if (apiKey) {
                headers['Authorization'] = `Bearer ${apiKey}`;
            }

            const response = await axios.post<ChatResponse>(
                `${apiUrl}/chat/`,
                formData,
                { headers, signal: controller.signal },
            );
            const data = response.data;

            // Process results - filter out non-tabular data
            let processedResults: Record<string, unknown>[] = [];
            if (Array.isArray(data.results)) {
                processedResults = data.results;
            } else if (data.results && typeof data.results === 'object') {
                const keys = Object.keys(data.results);
                if (!keys.every(key => /^\d+$/.test(key))) {
                    processedResults = [data.results];
                }
            }

            setChatHistory(prev => prev.map(chat =>
                chat.id === newChat.id ? {
                    ...chat,
                    answer: data.answer || 'No answer provided.',
                    sql: data.sql_executed || data.sql || '',
                    results: processedResults,
                    follow_up_questions: data.follow_up_questions || [],
                    results_truncated: data.results_truncated,
                    latency_ms: data.latency_ms,
                    row_cap: data.row_cap,
                    isTyping: false,
                } : chat
            ));
        } catch (err: unknown) {
            const errorMessage = getErrorMessage(err, timedOut);
            setError(errorMessage);
            setChatHistory(prev => prev.map(chat =>
                chat.id === newChat.id ? {
                    ...chat,
                    answer: `Sorry, there was an error: ${errorMessage}`,
                    isTyping: false,
                } : chat
            ));
        } finally {
            window.clearTimeout(timeoutId);
            abortControllerRef.current = null;
            setIsLoading(false);
        }
        return true;
    };

    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        void sendQuestion(userInput, false);
    };

    const handleFollowUpClick = (question: string) => {
        void sendQuestion(question, true);
    };

    const handleCancelRequest = () => {
        abortControllerRef.current?.abort();
    };

    const handleClearChat = () => {
        abortControllerRef.current?.abort();
        setChatHistory([]);
        setError(null);
    };

    const handleDbPathChange = (path: string) => {
        setDbPath(path);
        setDbFile(null); // A typed server path replaces any picked file.
        setError(null); // Clear error when path changes
    };

    const handleDbFileChange = (file: File | null) => {
        setDbFile(file);
        setDbPath('');
        setError(null);
    };

    const handleSaveSettings = (settings: { apiUrl: string; apiKey: string }) => {
        setApiUrl(settings.apiUrl);
        setApiKey(settings.apiKey);
        try {
            localStorage.setItem(API_URL_KEY, settings.apiUrl);
            localStorage.setItem(API_KEY_KEY, settings.apiKey);
        } catch {
            // Best-effort persistence.
        }
    };

    const toggleSidebar = () => {
        setSidebarOpen(!sidebarOpen);
    };

    return (
        <div className="flex h-screen overflow-hidden">
            <Sidebar
                isOpen={sidebarOpen}
                toggleSidebar={toggleSidebar}
                inputMethod={inputMethod}
                setInputMethod={setInputMethod}
                dbFile={dbFile}
                handleDbFileChange={handleDbFileChange}
                dbPath={dbPath}
                handleDbPathChange={handleDbPathChange}
                dbUrl={dbUrl}
                setDbUrl={setDbUrl}
            />
            <div className="flex-1 flex flex-col overflow-hidden">
                <Header
                    toggleSidebar={toggleSidebar}
                    isSidebarOpen={sidebarOpen}
                    apiUrl={apiUrl}
                    apiKey={apiKey}
                    onSaveSettings={handleSaveSettings}
                />
                <ChatArea
                    chatHistory={chatHistory}
                    onFollowUpClick={handleFollowUpClick}
                    isLoading={isLoading}
                    onCancelRequest={handleCancelRequest}
                    onClearChat={handleClearChat}
                />
                <InputArea
                    userInput={userInput}
                    setUserInput={setUserInput}
                    handleSubmit={handleSubmit}
                    isLoading={isLoading}
                    error={error}
                    onClearError={() => setError(null)}
                    onCancelRequest={handleCancelRequest}
                    apiUrl={`${apiUrl}/chat/`}
                />
            </div>
        </div>
    );
};

export default App;
