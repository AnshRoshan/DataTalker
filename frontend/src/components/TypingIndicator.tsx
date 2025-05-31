import React from 'react';

const TypingIndicator: React.FC = () => {
    return (
        <div className="flex items-center space-x-2 p-3">
            <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gradient-to-r from-purple-400 to-purple-600 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                <div className="w-2 h-2 bg-gradient-to-r from-purple-400 to-purple-600 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                <div className="w-2 h-2 bg-gradient-to-r from-purple-400 to-purple-600 rounded-full animate-bounce"></div>
            </div>
            <span className="text-sm text-gray-500 italic">Assistant is thinking...</span>
        </div>
    );
};

export default TypingIndicator;