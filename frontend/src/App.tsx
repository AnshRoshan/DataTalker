import React, { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import type {
  ActiveDbRef,
  ChatMessageData,
  ChatResponse,
  Connection,
  HealthStatus,
  NewConnectionInput,
  ViewId,
} from './types';
import {
  createConnection,
  checkConnection,
  deleteConnection,
  fetchConnections,
  fetchHealth,
  getErrorMessage,
  sendChat,
} from './lib/api';
import {
  loadActiveDbRef,
  loadApiKey,
  loadApiUrl,
  loadChatHistory,
  saveActiveDbRef,
  saveChatHistory,
  saveSettings,
} from './lib/storage';
import IconRail from './components/IconRail';
import TopBar from './components/TopBar';
import SettingsModal from './components/SettingsModal';
import ChatView from './components/chat/ChatView';

// The schema explorer pulls in the graph library; keep it out of the main chunk.
const ConnectionsView = lazy(() => import('./components/connections/ConnectionsView'));
const SchemaView = lazy(() => import('./components/schema/SchemaView'));

const ViewFallback: React.FC = () => (
  <div className="flex flex-1 items-center justify-center">
    <span className="font-display text-[12px] text-fg/40">Loading...</span>
  </div>
);

const HEALTH_POLL_MS = 30_000;

const App: React.FC = () => {
  const [view, setView] = useState<ViewId>('chat');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [apiUrl, setApiUrl] = useState<string>(() => loadApiUrl());
  const [apiKey, setApiKey] = useState<string>(() => loadApiKey());

  // Chat state (persisted, last 50)
  const [messages, setMessages] = useState<ChatMessageData[]>(() => loadChatHistory());
  const [isLoading, setIsLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Active database reference (sent as connection_id when it is a saved connection)
  const [activeRef, setActiveRef] = useState<ActiveDbRef | null>(() => loadActiveDbRef());
  /** Success/failure of the last request made with a non-connection ref. */
  const [quickRefOk, setQuickRefOk] = useState<boolean | null>(null);

  // Saved connections
  const [connections, setConnections] = useState<Connection[]>([]);
  const [connectionsLoading, setConnectionsLoading] = useState(false);
  const [connectionsError, setConnectionsError] = useState<string | null>(null);

  // Health badge
  const [health, setHealth] = useState<HealthStatus>('checking');

  /* ---------------------------- persistence ---------------------------- */

  useEffect(() => {
    saveChatHistory(messages);
  }, [messages]);

  useEffect(() => {
    saveActiveDbRef(activeRef);
  }, [activeRef]);

  /* ------------------------------ health ------------------------------- */

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      const status = await fetchHealth(apiUrl, apiKey);
      if (!cancelled) setHealth(status);
    };
    void poll();
    const id = window.setInterval(() => void poll(), HEALTH_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [apiUrl, apiKey]);

  /* ---------------------------- connections ---------------------------- */

  const refreshConnections = useCallback(async () => {
    setConnectionsLoading(true);
    setConnectionsError(null);
    try {
      const data = await fetchConnections(apiUrl, apiKey);
      setConnections(data.connections ?? []);
    } catch (err) {
      setConnectionsError(getErrorMessage(err));
    } finally {
      setConnectionsLoading(false);
    }
  }, [apiUrl, apiKey]);

  // Load the connection list once per apiUrl/apiKey change.
  useEffect(() => {
    setConnections([]);
    void refreshConnections();
  }, [refreshConnections]);

  const handleCreateConnection = useCallback(
    async (input: NewConnectionInput): Promise<Connection> => {
      try {
        const created = await createConnection(apiUrl, apiKey, input);
        setConnections(prev => [...prev, created]);
        return created;
      } catch (err) {
        throw new Error(getErrorMessage(err));
      }
    },
    [apiUrl, apiKey],
  );

  const handleCheckConnection = useCallback(
    async (id: number) => {
      try {
        const updated = await checkConnection(apiUrl, apiKey, id);
        setConnections(prev =>
          prev.map(c =>
            c.id === id
              ? { ...c, last_checked_at: updated.last_checked_at, last_status: updated.last_status ?? c.last_status }
              : c,
          ),
        );
      } catch (err) {
        throw new Error(getErrorMessage(err));
      }
    },
    [apiUrl, apiKey],
  );

  const handleDeleteConnection = useCallback(
    async (id: number) => {
      try {
        await deleteConnection(apiUrl, apiKey, id);
        setConnections(prev => prev.filter(c => c.id !== id));
        setActiveRef(ref => (ref?.kind === 'connection' && ref.id === id ? null : ref));
      } catch (err) {
        throw new Error(getErrorMessage(err));
      }
    },
    [apiUrl, apiKey],
  );

  const handleSetActiveConnection = useCallback((conn: Connection) => {
    setActiveRef({ kind: 'connection', id: conn.id, name: conn.name });
    setQuickRefOk(null);
  }, []);

  const handleQuickAttach = useCallback((ref: ActiveDbRef) => {
    setActiveRef(ref);
    setQuickRefOk(null);
  }, []);

  /* ------------------------------- chat -------------------------------- */

  const connectionStatusOk = useMemo(() => {
    if (activeRef?.kind !== 'connection') return null;
    const conn = connections.find(c => c.id === activeRef.id);
    if (!conn || !conn.last_status) return null;
    return conn.last_status.ok;
  }, [activeRef, connections]);

  const refOk: boolean | null =
    activeRef?.kind === 'connection' ? connectionStatusOk : quickRefOk;

  const sendQuestion = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || isLoading) return;
      if (!activeRef) {
        setChatError('Attach a database first. Open Connections to pick one or quick-attach a file.');
        return;
      }

      setChatError(null);
      setIsLoading(true);

      const newChat: ChatMessageData = {
        id: crypto.randomUUID(),
        question: trimmed,
        answer: '',
        sql: '',
        results: [],
        isTyping: true,
      };
      setMessages(prev => [...prev, newChat]);

      const controller = new AbortController();
      abortRef.current = controller;
      let timedOut = false;
      const timeoutId = window.setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, 120_000);

      try {
        const history = messages
          .filter(m => !m.isTyping && m.answer)
          .slice(-5)
          .map(m => ({ question: m.question, answer: m.answer, sql: m.sql }));

        const data: ChatResponse = await sendChat({
          apiUrl,
          apiKey,
          question: trimmed,
          dbRef: activeRef,
          history,
          signal: controller.signal,
        });

        let results: Record<string, unknown>[] | Record<string, unknown> = [];
        if (Array.isArray(data.results)) {
          results = data.results;
        } else if (data.results && typeof data.results === 'object') {
          const keys = Object.keys(data.results);
          results = keys.every(k => /^\d+$/.test(k)) ? results : data.results;
        }

        setMessages(prev =>
          prev.map(m =>
            m.id === newChat.id
              ? {
                  ...m,
                  answer: data.answer || 'No answer provided.',
                  sql: data.sql_executed || data.sql || '',
                  results,
                  follow_up_questions: data.follow_up_questions || [],
                  results_truncated: data.results_truncated,
                  sql_executed: data.sql_executed,
                  latency_ms: data.latency_ms,
                  row_cap: data.row_cap,
                  isTyping: false,
                }
              : m,
          ),
        );
        if (activeRef.kind !== 'connection') setQuickRefOk(true);
      } catch (err) {
        const message = getErrorMessage(err, timedOut);
        if (!axios.isCancel(err)) {
          // User cancels do not need a banner; they are visible in the composer.
          setChatError(message);
        }
        if (activeRef.kind !== 'connection') setQuickRefOk(false);
        setMessages(prev =>
          prev.map(m =>
            m.id === newChat.id
              ? {
                  ...m,
                  answer: `Sorry, there was an error: ${message}`,
                  isTyping: false,
                }
              : m,
          ),
        );
      } finally {
        window.clearTimeout(timeoutId);
        abortRef.current = null;
        setIsLoading(false);
      }
    },
    [activeRef, apiUrl, apiKey, isLoading, messages],
  );

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const handleClearChat = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setChatError(null);
  }, []);

  const handleSaveSettings = useCallback((s: { apiUrl: string; apiKey: string }) => {
    const normalizedUrl = s.apiUrl.replace(/\/$/, '');
    setApiUrl(normalizedUrl);
    setApiKey(s.apiKey);
    setHealth('checking');
    saveSettings(normalizedUrl, s.apiKey);
  }, []);

  /* ------------------------------- render ------------------------------ */

  return (
    <div className="ambient-bg flex h-dvh overflow-hidden text-fg">
      <IconRail active={view} onChange={setView} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          activeRef={activeRef}
          refOk={refOk}
          health={health}
          onOpenSettings={() => setSettingsOpen(true)}
        />
        {view === 'chat' ? (
          <ChatView
            messages={messages}
            isLoading={isLoading}
            error={chatError}
            dbRef={activeRef}
            refOk={refOk}
            onSend={q => void sendQuestion(q)}
            onCancel={handleCancel}
            onDismissError={() => setChatError(null)}
            onClearChat={handleClearChat}
            onGoToConnections={() => setView('connections')}
          />
        ) : view === 'connections' ? (
          <Suspense fallback={<ViewFallback />}>
            <ConnectionsView
              connections={connections}
              isLoading={connectionsLoading}
              loadError={connectionsError}
              activeRef={activeRef}
              onReload={() => void refreshConnections()}
              onSetActive={handleSetActiveConnection}
              onCreate={handleCreateConnection}
              onCheck={handleCheckConnection}
              onDelete={handleDeleteConnection}
              onQuickAttach={handleQuickAttach}
            />
          </Suspense>
        ) : (
          <Suspense fallback={<ViewFallback />}>
            <SchemaView apiUrl={apiUrl} apiKey={apiKey} dbRef={activeRef} />
          </Suspense>
        )}
      </div>
      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        apiUrl={apiUrl}
        apiKey={apiKey}
        onSave={handleSaveSettings}
      />
    </div>
  );
};

export default App;
