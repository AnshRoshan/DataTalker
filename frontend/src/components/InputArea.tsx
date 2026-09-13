import React from 'react';

interface InputAreaProps {
    userInput: string;
    setUserInput: (input: string) => void;
    handleSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
    isLoading: boolean;
    error: string | null;
    onClearError: () => void;
    onCancelRequest: () => void;
    apiUrl: string;
}

const InputArea: React.FC<InputAreaProps> = ({
    userInput,
    setUserInput,
    handleSubmit,
    isLoading,
    error,
    onClearError,
    onCancelRequest,
    apiUrl,
}) => {
    return (
        <footer className="bg-white/80 backdrop-blur-sm border-t border-gray-200 p-6">
            <div className="max-w-4xl mx-auto">
                {error && (
                    <div className="mb-4 p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl flex items-center text-sm animate-fadeIn">
                        <i className="fas fa-exclamation-triangle mr-3 text-red-500"></i>
                        <span>{error}</span>
                        <button
                            onClick={onClearError}
                            className="ml-auto text-red-500 hover:text-red-700"
                            aria-label="Dismiss error"
                        >
                            <i className="fas fa-times"></i>
                        </button>
                    </div>
                )}

                <form onSubmit={handleSubmit} className="flex space-x-3">
                    <div className="flex-1 relative group">
                        <input
                            type="text"
                            value={userInput}
                            onChange={(e) => setUserInput(e.target.value)}
                            placeholder="Ask something about your database..."
                            className="w-full px-5 py-4 pr-12 border-2 border-gray-200 rounded-2xl focus:outline-none focus:ring-4 focus:ring-blue-100 focus:border-blue-500 shadow-sm hover:border-gray-300 transition-all text-gray-700 placeholder-gray-400"
                            disabled={isLoading}
                        />
                        {userInput && (
                            <button
                                type="button"
                                className="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                                onClick={() => setUserInput('')}
                                aria-label="Clear input"
                            >
                                <i className="fas fa-times-circle text-lg"></i>
                            </button>
                        )}
                    </div>
                    {isLoading ? (
                        <button
                            type="button"
                            onClick={onCancelRequest}
                            className="px-6 py-4 rounded-2xl flex items-center justify-center font-medium border-2 border-red-200 text-red-600 hover:bg-red-50 hover:border-red-300 transition-all duration-200"
                            aria-label="Cancel request"
                        >
                            <i className="fas fa-stop mr-0 sm:mr-2"></i>
                            <span className="hidden sm:inline">Cancel</span>
                        </button>
                    ) : (
                        <button
                            type="submit"
                            disabled={!userInput.trim()}
                            className={`px-6 py-4 rounded-2xl flex items-center justify-center font-medium ${
                                !userInput.trim()
                                    ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                                    : 'bg-gradient-to-r from-blue-600 to-blue-700 text-white hover:from-blue-700 hover:to-blue-800 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5'
                            } transition-all duration-200`}
                        >
                            <i className="fas fa-paper-plane mr-0 sm:mr-2"></i>
                            <span className="hidden sm:inline">Send</span>
                        </button>
                    )}
                </form>

                <div className="mt-3 text-xs text-gray-400 flex items-center justify-center">
                    <div className="flex items-center">
                        <div className="w-2 h-2 bg-green-400 rounded-full mr-2 animate-pulse"></div>
                        <span>Connected to {apiUrl}</span>
                    </div>
                </div>
            </div>
        </footer>
    );
};

export default InputArea;
