import React, { useState } from 'react';
import { type InputMethod } from '../types';

interface SidebarProps {
    isOpen: boolean;
    toggleSidebar: () => void;
    inputMethod: InputMethod;
    setInputMethod: (method: InputMethod) => void;
    dbFile: File | null;
    handleDbFileChange: (file: File | null) => void;
    dbPath: string;
    handleDbPathChange: (path: string) => void;
    dbUrl: string;
    setDbUrl: (url: string) => void;
}

const ALLOWED_EXTENSIONS = ['.db', '.sqlite', '.sqlite3'];

const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const Sidebar: React.FC<SidebarProps> = ({
    isOpen,
    toggleSidebar,
    inputMethod,
    setInputMethod,
    dbFile,
    handleDbFileChange,
    dbPath,
    handleDbPathChange,
    dbUrl,
    setDbUrl,
}) => {
    const [fileError, setFileError] = useState<string | null>(null);
    const [showAdvanced, setShowAdvanced] = useState(false);

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
        const file = e.target.files?.[0] ?? null;
        // Clear the input so selecting the same file again still fires change
        e.target.value = '';
        if (!file) return;

        const dotIndex = file.name.lastIndexOf('.');
        const extension = dotIndex >= 0 ? file.name.slice(dotIndex).toLowerCase() : '';
        if (!ALLOWED_EXTENSIONS.includes(extension)) {
            setFileError('Unsupported file type. Please choose a .db, .sqlite, or .sqlite3 file.');
            handleDbFileChange(null);
            return;
        }
        setFileError(null);
        handleDbFileChange(file);
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
                <div className={`p-6 h-full flex flex-col overflow-y-auto custom-scrollbar ${isOpen ? 'opacity-100' : 'opacity-0'} transition-opacity duration-300`}>
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
                            Local File
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

                            {/* Primary: real file upload from the user's machine */}
                            <label
                                className="
                                    flex items-center justify-center px-4 py-4 bg-blue-600/20 border border-dashed border-blue-500/40
                                    rounded-xl text-blue-300 hover:bg-blue-600/30 hover:text-blue-200
                                    transition-all duration-200 text-sm font-medium cursor-pointer
                                "
                            >
                                <i className="fas fa-upload mr-2"></i>
                                {dbFile ? 'Choose a different file' : 'Choose database file'}
                                <input
                                    type="file"
                                    className="hidden"
                                    accept=".db,.sqlite,.sqlite3"
                                    onChange={handleFileSelect}
                                />
                            </label>

                            {fileError && (
                                <div className="flex items-center space-x-2 text-red-400 text-xs">
                                    <i className="fas fa-exclamation-triangle"></i>
                                    <span>{fileError}</span>
                                </div>
                            )}

                            {dbFile && (
                                <div className="flex items-center space-x-3 bg-gray-700/50 border border-gray-600 rounded-xl p-3">
                                    <div className="p-2 bg-blue-500/20 rounded-lg">
                                        <i className="fas fa-file-code text-blue-400"></i>
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-white truncate" title={dbFile.name}>
                                            {dbFile.name}
                                        </p>
                                        <p className="text-xs text-gray-400">{formatFileSize(dbFile.size)}</p>
                                    </div>
                                    <button
                                        onClick={() => handleDbFileChange(null)}
                                        className="p-1.5 rounded-lg hover:bg-gray-600 transition-colors"
                                        aria-label="Remove selected file"
                                    >
                                        <i className="fas fa-times text-gray-400 hover:text-white"></i>
                                    </button>
                                </div>
                            )}

                            {/* Advanced: point the backend at a path on the server's filesystem */}
                            <button
                                onClick={() => setShowAdvanced(!showAdvanced)}
                                className="text-xs text-gray-400 hover:text-gray-200 transition-colors flex items-center"
                                aria-expanded={showAdvanced}
                            >
                                <i className={`fas fa-chevron-${showAdvanced ? 'down' : 'right'} mr-1.5`}></i>
                                Advanced: server path
                            </button>
                            {showAdvanced && (
                                <div className="space-y-2">
                                    <div className="relative">
                                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                            <i className="fas fa-file-code text-gray-400"></i>
                                        </div>
                                        <input
                                            type="text"
                                            value={dbPath}
                                            onChange={(e) => handleDbPathChange(e.target.value)}
                                            placeholder="Absolute path on the server: C:\path\to\file.db"
                                            className={`
                                                w-full pl-10 pr-4 py-3 bg-gray-700/50 border rounded-xl text-white placeholder-gray-400 text-sm
                                                focus:outline-none focus:ring-2 focus:border-transparent transition-all duration-200
                                                ${dbPath && !isAbsolutePath(dbPath)
                                                    ? 'border-red-500 focus:ring-red-500'
                                                    : 'border-gray-600 focus:ring-blue-500'
                                                }
                                            `}
                                        />
                                    </div>
                                    {dbPath && !isAbsolutePath(dbPath) && (
                                        <div className="flex items-center space-x-2 text-red-400 text-xs">
                                            <i className="fas fa-exclamation-triangle"></i>
                                            <span>Path must be absolute (e.g., C:\path\to\file.db or /path/to/file.db)</span>
                                        </div>
                                    )}
                                    <p className="text-xs text-gray-400">
                                        Path on the <span className="font-semibold">server's</span> filesystem,
                                        confined to the backend's configured DB directory. Use the file picker
                                        above to upload a file from your own machine instead.
                                    </p>
                                </div>
                            )}
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
                            {inputMethod === 'upload' && dbFile ? (
                                <div className="flex items-center space-x-3">
                                    <div className="p-2 bg-blue-500/20 rounded-lg">
                                        <i className="fas fa-file-code text-blue-400"></i>
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-white truncate" title={dbFile.name}>
                                            {dbFile.name}
                                        </p>
                                        <p className="text-xs text-gray-400">Uploaded file · {formatFileSize(dbFile.size)}</p>
                                    </div>
                                </div>
                            ) : inputMethod === 'upload' && dbPath ? (
                                <div className="flex items-center space-x-3">
                                    <div className="p-2 bg-blue-500/20 rounded-lg">
                                        <i className="fas fa-file-alt text-blue-400"></i>
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-white truncate" title={dbPath}>
                                            {dbPath.split(/[\\/]/).pop() || dbPath}
                                        </p>
                                        <p className="text-xs text-gray-400">Server file path</p>
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
