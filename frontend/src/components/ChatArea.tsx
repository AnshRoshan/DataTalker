import React from 'react';
import { type ChatMessageData } from '../types';
import ChatMessage from './ChatMessage';

interface ChatAreaProps {
    chatHistory: ChatMessageData[];
    onFollowUpClick?: (question: string) => void;
    isLoading?: boolean;
    onCancelRequest?: () => void;
    onClearChat?: () => void;
}

const WelcomeMessage: React.FC = () => (
    <div className="h-fit flex flex-col items-center justify-center text-center p-8">
        <div className="w-32 h-32 bg-gradient-to-br from-blue-400 to-blue-600 rounded-full flex items-center justify-center mb-6 shadow-lg animate-pulse py-4 px-2">
            <i className="fas fa-database text-white text-5xl"></i>
        </div>
        <h2 className="text-3xl font-bold text-gray-800 mb-3">Welcome to Talk to Data</h2>
        <p className="text-gray-600 max-w-lg text-lg">
            Ask questions about your database in natural language and get instant SQL queries and results.
        </p>
        <div className="mt-8 p-6 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl max-w-lg w-full shadow-sm border border-blue-100">
            <h3 className="font-semibold text-blue-900 mb-4 flex items-center">
                <i className="fas fa-lightbulb text-yellow-500 mr-2"></i>
                Example Questions
            </h3>
            <ul className="space-y-3 text-left">
                <li className="text-sm text-gray-700 bg-white p-3 rounded-lg shadow-sm hover:shadow-md transition-shadow cursor-pointer">
                    <i className="fas fa-search text-blue-500 mr-2"></i>
                    "Show me all customers from New York"
                </li>
                <li className="text-sm text-gray-700 bg-white p-3 rounded-lg shadow-sm hover:shadow-md transition-shadow cursor-pointer">
                    <i className="fas fa-chart-line text-green-500 mr-2"></i>
                    "What's the average order value?"
                </li>
                <li className="text-sm text-gray-700 bg-white p-3 rounded-lg shadow-sm hover:shadow-md transition-shadow cursor-pointer">
                    <i className="fas fa-box text-orange-500 mr-2"></i>
                    "List products with less than 10 units in stock"
                </li>
            </ul>
        </div>
    </div>
);

const ChatArea: React.FC<ChatAreaProps> = ({ chatHistory, onFollowUpClick, isLoading, onCancelRequest, onClearChat }) => {
    const messagesEndRef = React.useRef<HTMLDivElement>(null);

    React.useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [chatHistory]);

    return (
        <main className="flex-1 overflow-y-auto custom-scrollbar bg-gradient-to-b from-gray-50 to-white">
            {chatHistory.length === 0 ? (
                <WelcomeMessage />
            ) : (
                <div className="max-w-4xl mx-auto p-6 space-y-6">
                    {onClearChat && (
                        <div className="flex justify-end">
                            <button
                                onClick={onClearChat}
                                className="px-3 py-1.5 rounded-lg text-xs text-gray-400 hover:text-red-600 hover:bg-red-50 transition-all duration-200 flex items-center"
                                aria-label="Clear chat history"
                            >
                                <i className="fas fa-trash-alt mr-1.5"></i>
                                Clear chat
                            </button>
                        </div>
                    )}
                    {chatHistory.map((chatItem, index) => {
                        const isLatest = index === chatHistory.length - 1;
                        const shouldShowFollowUp = isLatest && !chatItem.isTyping && onFollowUpClick;

                        return (
                            <div key={chatItem.id} className="space-y-4">
                                <ChatMessage message={chatItem} isUser={true} />
                                <ChatMessage
                                    message={chatItem}
                                    isUser={false}
                                    onFollowUpClick={shouldShowFollowUp ? onFollowUpClick : undefined}
                                />
                            </div>
                        );
                    })}
                    {isLoading && onCancelRequest && (
                        <div className="flex justify-center">
                            <button
                                onClick={onCancelRequest}
                                className="px-4 py-2 rounded-xl text-sm text-gray-500 bg-white border border-gray-200 hover:text-red-600 hover:border-red-200 hover:bg-red-50 transition-all duration-200 shadow-sm flex items-center"
                                aria-label="Cancel request"
                            >
                                <i className="fas fa-stop mr-2"></i>
                                Cancel request
                            </button>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>
            )}
        </main>
    );
};

export default ChatArea;
