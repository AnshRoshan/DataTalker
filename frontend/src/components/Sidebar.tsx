import React from 'react';
import { type InputMethod } from '../types';

interface SidebarProps {
    isOpen: boolean;
    toggleSidebar: () => void;
    inputMethod: InputMethod;
    setInputMethod: (method: InputMethod) => void;
    dbFile: File | null;
    handleFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
    dbUrl: string;
    setDbUrl: (url: string) => void;
}

const Sidebar: React.FC<SidebarProps> = ({
    isOpen,
    toggleSidebar,
    inputMethod,
    setInputMethod,
    dbFile,
    handleFileChange,
    dbUrl,
    setDbUrl,
}) => {
    return (
        <>
            {/* Backdrop for mobile */}
            {isOpen && (
                <div 
                    className="fixed inset-0 bg-black/50 z-40 lg:hidden"
                    onClick={toggleSidebar}
                />
            )}
            
            <div
                className={`
                    fixed lg:relative top-0 left-0 h-full z-50 lg:z-0
                    ${isOpen ? 'w-80' : 'w-0'}
                    bg-gradient-to-b from-gray-900 to-gray-800 text-white 
                    transition-all duration-300 ease-in-out overflow-hidden flex-shrink-0
                    shadow-2xl lg:shadow-xl
                `}
            >
                <div className={`p-6 h-full flex flex-col ${isOpen ? 'opacity-100' : 'opacity-0'} transition-opacity duration-300`}>
                    <div className="flex items-center justify-between mb-8">
                        <h2 className="text-2xl font-bold flex items-center">
                            <div className="relative mr-3">
                                <div className="absolute inset-0 bg-blue-500 rounded-lg blur opacity-50"></div>
                                <div className="relative bg-gradient-to-r from-blue-500 to-blue-600 p-2 rounded-lg">
                                    <i className="fas fa-database text-white"></i>
                                </div>
                            </div>
                            Database Setup
                        </h2>
                        <button
                            onClick={toggleSidebar}
                            className="p-2 rounded-lg hover:bg-gray-700 transition-all duration-200 group"
                            aria-label="Close sidebar"
                        >
                            <i className="fas fa-times text-xl text-gray-400 group-hover:text-white transition-colors"></i>
                        </button>
                    </div>

                <div className="mb-8">
                    <div className="bg-gray-700/50 p-1 rounded-xl flex space-x-1 mb-6">
                        <button
                            onClick={() => setInputMethod('upload')}
                            className={`
                                flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200
                                ${inputMethod === 'upload'
                                    ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg'
                                    : 'text-gray-300 hover:text-white hover:bg-gray-600/50'
                                }
                            `}
                        >
                            <i className="fas fa-upload mr-2"></i>
                            Upload File
                        </button>
                        <button
                            onClick={() => setInputMethod('url')}
                            className={`
                                flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200
                                ${inputMethod === 'url'
                                    ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg'
                                    : 'text-gray-300 hover:text-white hover:bg-gray-600/50'
                                }
                            `}
                        >
                            <i className="fas fa-link mr-2"></i>
                            Provide URL
                        </button>
                    </div>

                    {inputMethod === 'upload' ? (
                        <div className="space-y-3">
                            <label className="block text-sm font-semibold text-gray-200 mb-2">
                                Upload SQLite Database
                            </label>
                            <div className="flex items-center justify-center w-full">
                                <label className="
                                    relative flex flex-col items-center justify-center w-full h-40 
                                    border-2 border-gray-600 border-dashed rounded-xl cursor-pointer 
                                    bg-gray-700/30 hover:bg-gray-700/50 transition-all duration-200
                                    group overflow-hidden
                                ">
                                    <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 to-purple-500/10 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                                    <div className="relative flex flex-col items-center justify-center">
                                        <div className="p-3 bg-gray-700 rounded-full mb-3 group-hover:scale-110 transition-transform">
                                            <i className="fas fa-cloud-upload-alt text-3xl text-blue-400"></i>
                                        </div>
                                        <p className="text-sm text-gray-300 text-center px-4">
                                            {dbFile ? (
                                                <span className="text-blue-400 font-medium">{dbFile.name}</span>
                                            ) : (
                                                <>
                                                    <span className="font-medium">Click to upload</span>
                                                    <br />
                                                    <span className="text-xs text-gray-400">.db, .sqlite, .sqlite3</span>
                                                </>
                                            )}
                                        </p>
                                    </div>
                                    <input
                                        type="file"
                                        className="hidden"
                                        accept=".db,.sqlite,.sqlite3"
                                        onChange={handleFileChange}
                                    />
                                </label>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            <label className="block text-sm font-semibold text-gray-200 mb-2">
                                Database URL
                            </label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <i className="fas fa-globe text-gray-400"></i>
                                </div>
                                <input
                                    type="text"
                                    value={dbUrl}
                                    onChange={(e) => setDbUrl(e.target.value)}
                                    placeholder="https://example.com/database.db"
                                    className="
                                        w-full pl-10 pr-4 py-3 bg-gray-700/50 border border-gray-600 
                                        rounded-xl text-white placeholder-gray-400 
                                        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                                        transition-all duration-200
                                    "
                                />
                            </div>
                        </div>
                    )}
                </div>

                <div className="border-t border-gray-700 pt-6 mt-auto">
                    <h3 className="text-sm font-semibold text-gray-200 mb-3 flex items-center">
                        <i className="fas fa-info-circle mr-2 text-blue-400"></i>
                        Current Database
                    </h3>
                    <div className="relative">
                        <div className="absolute inset-0 bg-gradient-to-r from-blue-500/20 to-purple-500/20 rounded-xl blur"></div>
                        <div className="relative bg-gray-700/50 p-4 rounded-xl border border-gray-600">
                            {dbFile ? (
                                <div className="flex items-center space-x-3">
                                    <div className="p-2 bg-blue-500/20 rounded-lg">
                                        <i className="fas fa-file-alt text-blue-400"></i>
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-white truncate" title={dbFile.name}>
                                            {dbFile.name}
                                        </p>
                                        <p className="text-xs text-gray-400">Local file</p>
                                    </div>
                                </div>
                            ) : dbUrl ? (
                                <div className="flex items-center space-x-3">
                                    <div className="p-2 bg-green-500/20 rounded-lg">
                                        <i className="fas fa-link text-green-400"></i>
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-white truncate" title={dbUrl}>
                                            {dbUrl}
                                        </p>
                                        <p className="text-xs text-gray-400">Remote URL</p>
                                    </div>
                                </div>
                            ) : (
                                <div className="flex items-center space-x-3">
                                    <div className="p-2 bg-gray-600 rounded-lg">
                                        <i className="fas fa-database text-gray-400"></i>
                                    </div>
                                    <div>
                                        <p className="text-sm text-gray-400">No database selected</p>
                                        <p className="text-xs text-gray-500">Upload or provide URL above</p>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
        </>
    );
};

export default Sidebar;