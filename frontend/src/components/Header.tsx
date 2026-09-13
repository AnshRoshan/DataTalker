import React, { useState, useEffect, useRef } from 'react';
import type { HealthStatus } from '../types';
import Settings from './Settings';

interface HeaderProps {
    toggleSidebar: () => void;
    isSidebarOpen: boolean;
    apiUrl: string;
    apiKey: string;
    onSaveSettings: (settings: { apiUrl: string; apiKey: string }) => void;
}

const HEALTH_POLL_INTERVAL_MS = 30_000;
const HEALTH_CHECK_TIMEOUT_MS = 10_000;

const HEALTH_BADGE_STYLES: Record<HealthStatus, { badge: string; dot: string; label: string }> = {
    checking: {
        badge: 'from-gray-50 to-slate-50 border-gray-200',
        dot: 'bg-gray-400',
        label: 'Checking…',
    },
    connected: {
        badge: 'from-green-50 to-emerald-50 border-green-200',
        dot: 'bg-green-400',
        label: 'Connected',
    },
    disconnected: {
        badge: 'from-red-50 to-rose-50 border-red-200',
        dot: 'bg-red-400',
        label: 'Disconnected',
    },
};

const Header: React.FC<HeaderProps> = ({ toggleSidebar, isSidebarOpen, apiUrl, apiKey, onSaveSettings }) => {
    const [isScrolled, setIsScrolled] = useState(false);
    const [showSettings, setShowSettings] = useState(false);
    const [health, setHealth] = useState<HealthStatus>('checking');
    const healthCheckRef = useRef<AbortController | null>(null);

    useEffect(() => {
        const handleScroll = () => {
            setIsScrolled(window.scrollY > 10);
        };
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    // Real health check (FE-08): poll on mount, on apiUrl change, and every 30s.
    useEffect(() => {
        let disposed = false;

        const checkHealth = async () => {
            healthCheckRef.current?.abort();
            const controller = new AbortController();
            healthCheckRef.current = controller;
            const timeoutId = window.setTimeout(() => controller.abort(), HEALTH_CHECK_TIMEOUT_MS);
            try {
                // /health requires no auth.
                const response = await fetch(`${apiUrl}/health`, { signal: controller.signal });
                if (!disposed) {
                    setHealth(response.ok ? 'connected' : 'disconnected');
                }
            } catch {
                if (!disposed) {
                    setHealth('disconnected');
                }
            } finally {
                window.clearTimeout(timeoutId);
            }
        };

        setHealth('checking');
        void checkHealth();
        const intervalId = window.setInterval(() => void checkHealth(), HEALTH_POLL_INTERVAL_MS);

        return () => {
            disposed = true;
            window.clearInterval(intervalId);
            healthCheckRef.current?.abort();
        };
    }, [apiUrl]);

    const badge = HEALTH_BADGE_STYLES[health];

    return (
        <>
            <header className={`
                sticky top-0 z-50 transition-all duration-300
                ${isScrolled
                    ? 'bg-white/80 backdrop-blur-md shadow-lg'
                    : 'bg-white shadow-sm'
                }
            `}>
                <div className="px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-4">
                            {!isSidebarOpen && (
                                <button
                                    onClick={toggleSidebar}
                                    className="group relative p-2 rounded-xl hover:bg-gray-100 transition-all duration-200"
                                    aria-label="Toggle sidebar"
                                >
                                    <div className="flex flex-col space-y-1.5">
                                        <span className="block w-6 h-0.5 bg-gray-600 group-hover:bg-gray-900 transition-colors"></span>
                                        <span className="block w-6 h-0.5 bg-gray-600 group-hover:bg-gray-900 transition-colors"></span>
                                        <span className="block w-6 h-0.5 bg-gray-600 group-hover:bg-gray-900 transition-colors"></span>
                                    </div>
                                </button>
                            )}

                            <div className="flex items-center">
                                <div className="relative">
                                    <div className="absolute inset-0 bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg blur opacity-25"></div>
                                    <div className="relative bg-gradient-to-r from-blue-600 to-purple-600 px-4 py-2 rounded-lg">
                                        <i className="fas fa-database text-white text-xl"></i>
                                    </div>
                                </div>
                                <h1 className="ml-3 text-2xl font-bold bg-gradient-to-r from-gray-800 to-gray-600 bg-clip-text text-transparent">
                                    Talk to Data
                                </h1>
                            </div>
                        </div>

                        <div className="flex items-center space-x-4">
                            <div className="hidden sm:flex items-center space-x-2">
                                <div className={`flex items-center space-x-2 px-3 py-2 bg-gradient-to-r rounded-lg border ${badge.badge}`}>
                                    <div className={`w-2 h-2 rounded-full ${health === 'disconnected' ? '' : 'animate-pulse'} ${badge.dot}`}></div>
                                    <span className={`text-sm font-medium ${health === 'connected' ? 'text-green-700' : health === 'disconnected' ? 'text-red-700' : 'text-gray-600'}`}>
                                        {badge.label}
                                    </span>
                                </div>
                                <div className="px-3 py-2 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-200">
                                    <span className="text-sm font-medium text-blue-700">FastAPI</span>
                                </div>
                            </div>

                            <button
                                onClick={() => setShowSettings(true)}
                                className="group p-2 rounded-lg hover:bg-gray-100 transition-all duration-200 relative"
                                aria-label="Settings"
                            >
                                <i className="fas fa-cog text-gray-600 group-hover:text-gray-900 transition-colors group-hover:rotate-90 duration-300"></i>
                                <span className="absolute -bottom-8 right-0 text-xs bg-gray-800 text-white px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                                    Settings
                                </span>
                            </button>
                        </div>
                    </div>
                </div>
            </header>

            <Settings
                isOpen={showSettings}
                onClose={() => setShowSettings(false)}
                apiUrl={apiUrl}
                apiKey={apiKey}
                onSave={onSaveSettings}
            />
        </>
    );
};

export default Header;
