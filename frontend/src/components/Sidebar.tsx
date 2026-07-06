import React from 'react';
import { type InputMethod } from '../types';

interface SidebarProps {
    isOpen: boolean;
    toggleSidebar: () => void;
    inputMethod: InputMethod;
    setInputMethod: (method: InputMethod) => void;
    dbPath: string;
    handleDbPathChange: (path: string) => void;
    dbUrl: string;
    setDbUrl: (url: string) => void;
}

const Sidebar: React.FC<SidebarProps> = ({
    isOpen,
    toggleSidebar,
    inputMethod,
    setInputMethod,
    dbPath,
    handleDbPathChange,
    dbUrl,
    setDbUrl,
}) => {
    const isAbsolutePath = (path: string): boolean => {
        // Check for Windows absolute paths (C:\, D:\, etc.)
        if (/^[A-Za-z]:\\/.test(path)) return true;
        // Check for Unix/Linux absolute paths (starting with /)
        if (path.startsWith('/')) return true;
        // Check for UNC paths (\\server\share)
        if (path.startsWith('\\\\')) return true;
        return false;
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];
            const fileName = file.name;
            
            // Since browsers can't provide the full path for security reasons,
            // we'll show the filename and prompt the user to provide the full absolute path
            alert(`File selected: ${fileName}\n\nDue to browser security restrictions, please manually enter the complete absolute path to this file in the input field.\n\nExample formats:\n- Windows: C:\\path\\to\\${fileName}\n- Linux/Mac: /path/to/${fileName}`);
            
            // Clear the file input to allow selecting the same file again
            e.target.value = '';
        }
    };

    const handlePathChange = (path: string) => {
        handleDbPathChange(path);
    };
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
                            <i className="fas fa-folder-open mr-2"></i>
                            Local File Path
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
                            <label htmlFor="dbPathInput" className="block text-sm font-semibold text-gray-200 mb-2">
                                Local SQLite Database Path
                            </label>
                            <div className="space-y-3">
                                <div className="relative">
                                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                        <i className="fas fa-file-code text-gray-400"></i>
                                    </div>
                                    <input
                                        id="dbPathInput"
                                        type="text"
                                        value={dbPath}
                                        onChange={(e) => handlePathChange(e.target.value)}
                                        placeholder="Enter absolute path: C:\path\to\file.db or /path/to/file.db"
                                        className={`
                                            w-full pl-10 pr-16 py-3 bg-gray-700/50 border rounded-xl text-white placeholder-gray-400 
                                            focus:outline-none focus:ring-2 focus:border-transparent transition-all duration-200
                                            ${dbPath && !isAbsolutePath(dbPath) 
                                                ? 'border-red-500 focus:ring-red-500' 
                                                : 'border-gray-600 focus:ring-blue-500'
                                            }
                                        `}
                                    />
                                    <div className="absolute inset-y-0 right-0 flex items-center pr-3">
                                        <label className="cursor-pointer p-1 hover:bg-gray-600 rounded transition-colors">
                                            <i className="fas fa-folder-open text-gray-400 hover:text-blue-400"></i>
                                            <input
                                                type="file"
                                                className="hidden"
                                                accept=".db,.sqlite,.sqlite3"
                                                onChange={handleFileSelect}
                                            />
                                        </label>
                                    </div>
                                </div>
                                <div className="flex space-x-2">
                                    <button
                                        onClick={() => {
                                            const input = document.createElement('input');
                                            input.type = 'file';
                                            input.accept = '.db,.sqlite,.sqlite3';
                                            input.onchange = (e) => handleFileSelect(e as any);
                                            input.click();
                                        }}
                                        className="
                                            flex-1 px-4 py-2 bg-blue-600/20 border border-blue-500/30 
                                            rounded-lg text-blue-400 hover:bg-blue-600/30 hover:text-blue-300
                                            transition-all duration-200 text-sm font-medium
                                            flex items-center justify-center space-x-2
                                        "
                                    >
                                        <i className="fas fa-folder-open"></i>
                                        <span>Browse Files</span>
                                    </button>
                                </div>
                                {dbPath && !isAbsolutePath(dbPath) && (
                                    <div className="flex items-center space-x-2 text-red-400 text-xs">
                                        <i className="fas fa-exclamation-triangle"></i>
                                        <span>Path must be absolute (e.g., C:\path\to\file.db or /path/to/file.db)</span>
                                    </div>
                                )}
                                <p className="text-xs text-gray-400">
                                    Enter the complete absolute path to your SQLite database file (.db, .sqlite, .sqlite3). 
                                    Click "Browse Files" to help locate the file, then manually enter its full path.
                                </p>
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
                                    placeholder="https://example.com/database.db or postgresql://user:pass@host:port/db"
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
                            {inputMethod === 'upload' && dbPath ? (
                                <div className="flex items-center space-x-3">
                                    <div className="p-2 bg-blue-500/20 rounded-lg">
                                        <i className="fas fa-file-alt text-blue-400"></i>
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-white truncate" title={dbPath}>
                                            {/* Show only filename from path */}
                                            {dbPath.split(/[\\/]/).pop() || dbPath}
                                        </p>
                                        <p className="text-xs text-gray-400">Local file path</p>
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