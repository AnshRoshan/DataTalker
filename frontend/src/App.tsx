import React, { useState, useEffect } from 'react';
import axios from 'axios';
import type { ChatMessageData, InputMethod } from './types';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import ChatArea from './components/ChatArea';
import InputArea from './components/InputArea';

const App: React.FC = () => {
  const [chatHistory, setChatHistory] = useState<ChatMessageData[]>([]);
  const [inputMethod, setInputMethod] = useState<InputMethod>("upload");
  const [dbPath, setDbPath] = useState<string>("");
  const [dbUrl, setDbUrl] = useState<string>("");
  const [userInput, setUserInput] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(true);

  // Use dynamic API URL from localStorage
  const getApiUrl = () => {
    const baseUrl = localStorage.getItem('apiUrl') || 'http://127.0.0.1:8000';
    return `${baseUrl}/chat/`;
  };

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

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!userInput.trim()) return;

    if (inputMethod === 'upload' && !dbPath.trim()) {
      setError("Please provide a local database file path first.");
      return;
    }
    if (inputMethod === 'upload' && dbPath.trim() && !isAbsolutePath(dbPath)) {
      setError("Database path must be absolute (e.g., C:\\path\\to\\file.db or /path/to/file.db).");
      return;
    }
    if (inputMethod === 'url' && !dbUrl.trim()) {
      setError("Please provide a database URL first.");
      return;
    }

    setIsLoading(true);
    setError(null);

    const newChat: ChatMessageData = {
      id: Date.now(),
      question: userInput,
      answer: "",
      sql: "",
      results: [],
      isTyping: true,
    };

    setChatHistory(prev => [...prev, newChat]);
    setUserInput("");

    try {
      const formData = new FormData();
      formData.append("question", newChat.question);

      if (inputMethod === "upload" && dbPath) {
        formData.append("db_path", dbPath);
      } else if (inputMethod === "url" && dbUrl) {
        if (isPostgresUrl(dbUrl)) {
          formData.append("db_connection_string", dbUrl);
        } else {
          formData.append("db_url", dbUrl);
        }
      }

      // Retrieve API key from localStorage
      const apiKey = localStorage.getItem('apiKey');
      const headers: Record<string, string> = {};
      // Add Authorization header if API key exists
      if (apiKey) {
        headers['Authorization'] = `Bearer ${apiKey}`;
      }

      const response = await axios.post<{ answer?: string; sql?: string; results?: Record<string, any>[]; follow_up_questions?: string[] }>(
        getApiUrl(),
        formData,
        { headers }
      );

      // Process results - filter out non-tabular data
      let processedResults = response.data.results || [];
      if (processedResults && !Array.isArray(processedResults)) {
        const keys = Object.keys(processedResults);
        if (keys.every(key => /^\d+$/.test(key))) {
          processedResults = [];
        }
      }

      setChatHistory(prev => prev.map(chat =>
        chat.id === newChat.id ? {
          ...chat,
          answer: response.data.answer || "No answer provided.",
          sql: response.data.sql || "",
          results: processedResults,
          follow_up_questions: response.data.follow_up_questions || [],
          isTyping: false,
        } : chat
      ));
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.response?.data?.error || "Failed to get response from server. Check if the backend is running.";
      setError(errorMessage);
      setChatHistory(prev => prev.map(chat =>
        chat.id === newChat.id ? {
          ...chat,
          answer: `Sorry, there was an error: ${errorMessage}`,
          isTyping: false,
        } : chat
      ));
    } finally {
      setIsLoading(false);
    }
  };

  const handleDbPathChange = (path: string) => {
    setDbPath(path);
    setError(null); // Clear error when path changes
  };

  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };

  const handleFollowUpClick = async (question: string) => {
    if (!question.trim()) return;

    if (inputMethod === 'upload' && !dbPath.trim()) {
      setError("Please provide a local database file path first.");
      return;
    }
    if (inputMethod === 'upload' && dbPath.trim() && !isAbsolutePath(dbPath)) {
      setError("Database path must be absolute (e.g., C:\\path\\to\\file.db or /path/to/file.db).");
      return;
    }
    if (inputMethod === 'url' && !dbUrl.trim()) {
      setError("Please provide a database URL first.");
      return;
    }

    setIsLoading(true);
    setError(null);

    const newChat: ChatMessageData = {
      id: Date.now(),
      question: question,
      answer: "",
      sql: "",
      results: [],
      isTyping: true,
    };

    setChatHistory(prev => [...prev, newChat]);

    try {
      const formData = new FormData();
      formData.append("question", newChat.question);

      if (inputMethod === "upload" && dbPath) {
        formData.append("db_path", dbPath);
      } else if (inputMethod === "url" && dbUrl) {
        if (isPostgresUrl(dbUrl)) {
          formData.append("db_connection_string", dbUrl);
        } else {
          formData.append("db_url", dbUrl);
        }
      }

      // Retrieve API key from localStorage
      const apiKey = localStorage.getItem('apiKey');
      const headers: Record<string, string> = {};
      // Add Authorization header if API key exists
      if (apiKey) {
        headers['Authorization'] = `Bearer ${apiKey}`;
      }

      const response = await axios.post<{ answer?: string; sql?: string; results?: Record<string, any>[]; follow_up_questions?: string[] }>(
        getApiUrl(),
        formData,
        { headers }
      );

      // Process results - filter out non-tabular data
      let processedResults = response.data.results || [];
      if (processedResults && !Array.isArray(processedResults)) {
        const keys = Object.keys(processedResults);
        if (keys.every(key => /^\d+$/.test(key))) {
          processedResults = [];
        }
      }

      setChatHistory(prev => prev.map(chat =>
        chat.id === newChat.id ? {
          ...chat,
          answer: response.data.answer || "No answer provided.",
          sql: response.data.sql || "",
          results: processedResults,
          follow_up_questions: response.data.follow_up_questions || [],
          isTyping: false,
        } : chat
      ));
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.response?.data?.error || "Failed to get response from server. Check if the backend is running.";
      setError(errorMessage);
      setChatHistory(prev => prev.map(chat =>
        chat.id === newChat.id ? {
          ...chat,
          answer: `Sorry, there was an error: ${errorMessage}`,
          isTyping: false,
        } : chat
      ));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        isOpen={sidebarOpen}
        toggleSidebar={toggleSidebar}
        inputMethod={inputMethod}
        setInputMethod={setInputMethod}
        dbPath={dbPath}
        handleDbPathChange={handleDbPathChange}
        dbUrl={dbUrl}
        setDbUrl={setDbUrl}
      />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header
          toggleSidebar={toggleSidebar}
          isSidebarOpen={sidebarOpen}
        />
        <ChatArea chatHistory={chatHistory} onFollowUpClick={handleFollowUpClick} />
        <InputArea
          userInput={userInput}
          setUserInput={setUserInput}
          handleSubmit={handleSubmit}
          isLoading={isLoading}
          error={error}
          apiUrl={getApiUrl()}
        />
      </div>
    </div>
  );
};

export default App;