import React, { useState, useEffect } from 'react';
import Settings from './Settings';

interface HeaderProps {
    toggleSidebar: () => void;
    isSidebarOpen: boolean;
}

const Header: React.FC<HeaderProps> = ({ toggleSidebar, isSidebarOpen }) => {
    const [isScrolled, setIsScrolled] = useState(false);
    const [showSettings, setShowSettings] = useState(false);

    useEffect(() => {
        const handleScroll = () => {
            setIsScrolled(window.scrollY > 10);
        };
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

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
                                <div className="flex items-center space-x-2 px-3 py-2 bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border border-green-200">
                                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                                    <span className="text-sm font-medium text-green-700">Connected</span>
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

            <Settings isOpen={showSettings} onClose={() => setShowSettings(false)} />
        </>
    );
};

export default Header;