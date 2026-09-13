import React from 'react';
import { type ChatMessageData } from '../types';
import TypingIndicator from './TypingIndicator';
import SQLCodeBlock from './SQLCodeBlock';
import ResultsTable from './ResultsTable';

// Utility function to parse markdown text
const parseMarkdown = (text: string): React.ReactNode[] => {
    const elements: React.ReactNode[] = [];
    let currentIndex = 0;
    let elementKey = 0;

    while (currentIndex < text.length) {
        // Check for horizontal rule (--- or ---)
        const hrMatch = text.slice(currentIndex).match(/^---+/);
        if (hrMatch && (currentIndex === 0 || text[currentIndex - 1] === '\n')) {
            elements.push(<hr key={elementKey++} className="my-3 border-gray-300" />);
            currentIndex += hrMatch[0].length;
            continue;
        }

        // Check for bold (**text**)
        const boldMatch = text.slice(currentIndex).match(/^\*\*(.*?)\*\*/);
        if (boldMatch) {
            elements.push(
                <strong key={elementKey++} className="font-bold">
                    {boldMatch[1]}
                </strong>
            );
            currentIndex += boldMatch[0].length;
            continue;
        }

        // Check for underline (__text__)
        const underlineMatch = text.slice(currentIndex).match(/^__(.*?)__/);
        if (underlineMatch) {
            elements.push(
                <span key={elementKey++} className="underline">
                    {underlineMatch[1]}
                </span>
            );
            currentIndex += underlineMatch[0].length;
            continue;
        }

        // Check for strikethrough (~~text~~)
        const strikethroughMatch = text.slice(currentIndex).match(/^~~(.*?)~~/);
        if (strikethroughMatch) {
            elements.push(
                <span key={elementKey++} className="line-through">
                    {strikethroughMatch[1]}
                </span>
            );
            currentIndex += strikethroughMatch[0].length;
            continue;
        }

        // Check for italic (*text*)
        const italicMatch = text.slice(currentIndex).match(/^\*(.*?)\*/);
        if (italicMatch) {
            elements.push(
                <em key={elementKey++} className="italic">
                    {italicMatch[1]}
                </em>
            );
            currentIndex += italicMatch[0].length;
            continue;
        }

        // Check for inline code (`text`)
        const codeMatch = text.slice(currentIndex).match(/^`(.*?)`/);
        if (codeMatch) {
            elements.push(
                <code key={elementKey++} className="bg-gray-100 px-1 py-0.5 rounded text-sm font-mono">
                    {codeMatch[1]}
                </code>
            );
            currentIndex += codeMatch[0].length;
            continue;
        }

        // Regular character
        elements.push(text[currentIndex]);
        currentIndex++;
    }

    return elements;
};

// Function to render a line with markdown parsing
const renderLineWithMarkdown = (line: string, key: number): React.ReactNode => {
    // Check if line is a horizontal rule
    if (line.trim().match(/^---+$/)) {
        return <hr key={key} className="my-3 border-gray-300" />;
    }

    // Check if line is a code block delimiter
    if (line.trim().match(/^```/)) {
        return (
            <div key={key} className="bg-gray-100 px-3 py-1 rounded text-sm font-mono border-l-4 border-gray-400">
                {line.replace(/```/g, '')}
            </div>
        );
    }

    // Check if line is a blockquote
    if (line.trim().match(/^>/)) {
        const quotedText = line.replace(/^>\s*/, '');
        return (
            <blockquote key={key} className="border-l-4 border-blue-400 pl-4 py-2 bg-blue-50 italic">
                {parseMarkdown(quotedText)}
            </blockquote>
        );
    }

    // Check if line is a header
    const headerMatch = line.trim().match(/^(#{1,6})\s+(.+)$/);
    if (headerMatch) {
        const level = headerMatch[1].length;
        const text = headerMatch[2];
        const headerClasses = {
            1: 'text-2xl font-bold mt-4 mb-2',
            2: 'text-xl font-bold mt-3 mb-2',
            3: 'text-lg font-semibold mt-3 mb-1',
            4: 'text-base font-semibold mt-2 mb-1',
            5: 'text-sm font-semibold mt-2 mb-1',
            6: 'text-xs font-semibold mt-1 mb-1'
        };

        const className = headerClasses[level as keyof typeof headerClasses];
        const content = parseMarkdown(text);

        switch (level) {
            case 1:
                return <h1 key={key} className={className}>{content}</h1>;
            case 2:
                return <h2 key={key} className={className}>{content}</h2>;
            case 3:
                return <h3 key={key} className={className}>{content}</h3>;
            case 4:
                return <h4 key={key} className={className}>{content}</h4>;
            case 5:
                return <h5 key={key} className={className}>{content}</h5>;
            case 6:
                return <h6 key={key} className={className}>{content}</h6>;
            default:
                return <h3 key={key} className={className}>{content}</h3>;
        }
    }

    // Check if line is a list item
    const listMatch = line.trim().match(/^[-*]\s+(.+)$/);
    if (listMatch) {
        const text = listMatch[1];
        return (
            <div key={key} className="flex items-start ml-4 mb-1">
                <span className="mr-2 mt-1.5 w-1.5 h-1.5 bg-gray-400 rounded-full flex-shrink-0"></span>
                <span>{parseMarkdown(text)}</span>
            </div>
        );
    }

    // Parse markdown in the line
    const parsedContent = parseMarkdown(line);

    return (
        <p key={key} className="leading-relaxed">
            {parsedContent}
        </p>
    );
};

interface ChatMessageProps {
    message: ChatMessageData;
    isUser: boolean;
    onFollowUpClick?: (question: string) => void;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message, isUser, onFollowUpClick }) => {
    if (isUser) {
        return (
            <div className="flex justify-end animate-fadeIn">
                <div className="max-w-3xl bg-gradient-to-r from-blue-600 to-blue-700 text-white p-5 rounded-2xl rounded-tr-sm shadow-lg">
                    <div className="flex items-center mb-2">
                        <div className="w-10 h-10 rounded-full bg-white/20 backdrop-blur flex items-center justify-center mr-3">
                            <i className="fas fa-user text-white"></i>
                        </div>
                        <span className="font-semibold text-blue-100">You</span>
                    </div>
                    <div className="text-white/95 leading-relaxed">
                        {message.question.split('\n').map((line, index) =>
                            renderLineWithMarkdown(line, index)
                        )}
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="flex justify-start animate-fadeIn">
            <div className="max-w-3xl bg-white p-5 rounded-2xl rounded-tl-sm shadow-lg border border-gray-100">
                <div className="flex items-center mb-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-400 to-purple-600 flex items-center justify-center mr-3 shadow-md">
                        <i className="fas fa-robot text-white"></i>
                    </div>
                    <span className="font-semibold text-gray-700">Assistant</span>
                </div>

                {message.isTyping ? (
                    <TypingIndicator />
                ) : (
                    <>
                        <div className="mt-2">
                            <div className="text-gray-700 space-y-2">
                                {(() => {
                                    const lines = message.answer.split('\n');
                                    const elements = [];
                                    let inTable = false;
                                    let tableLines = [];
                                    let inCodeBlock = false;
                                    let codeBlockLines = [];
                                    let codeBlockLanguage = '';

                                    for (let i = 0; i < lines.length; i++) {
                                        const line = lines[i];

                                        // Check for code block start/end
                                        if (line.trim().startsWith('```')) {
                                            if (!inCodeBlock) {
                                                // Starting a code block
                                                inCodeBlock = true;
                                                codeBlockLanguage = line.trim().substring(3);
                                                codeBlockLines = [];
                                            } else {
                                                // Ending a code block
                                                inCodeBlock = false;
                                                elements.push(
                                                    <div key={`code-${i}`} className="my-3">
                                                        <div className="bg-gray-900 rounded-lg overflow-hidden">
                                                            {codeBlockLanguage && (
                                                                <div className="bg-gray-800 px-4 py-2 text-xs text-gray-300 font-mono">
                                                                    {codeBlockLanguage}
                                                                </div>
                                                            )}
                                                            <pre className="bg-gray-100 p-4 text-sm font-mono text-gray-800 overflow-x-auto">
                                                                <code>{codeBlockLines.join('\n')}</code>
                                                            </pre>
                                                        </div>
                                                    </div>
                                                );
                                                codeBlockLines = [];
                                                codeBlockLanguage = '';
                                            }
                                            continue;
                                        }

                                        // If we're in a code block, collect lines
                                        if (inCodeBlock) {
                                            codeBlockLines.push(line);
                                            continue;
                                        }

                                        // Check if this line is part of a table
                                        if (line.includes('|') && line.trim() !== '') {
                                            if (!inTable) {
                                                inTable = true;
                                                tableLines = [];
                                            }
                                            tableLines.push(line);
                                        } else {
                                            // If we were in a table, render it
                                            if (inTable && tableLines.length > 0) {
                                                elements.push(
                                                    <div key={`table-${i}`} className="overflow-x-auto my-2">
                                                        <table className="min-w-full divide-y divide-gray-200 border border-gray-200">
                                                            {tableLines.map((tableLine, tableIndex) => {
                                                                const cells = tableLine.split('|').filter(cell => cell.trim() !== '');
                                                                const isHeader = tableIndex === 0;
                                                                const isSeparator = cells.every(cell => /^[-\s]+$/.test(cell));

                                                                if (isSeparator) return null;

                                                                return (
                                                                    <tr key={tableIndex} className={isHeader ? 'bg-gray-50' : ''}>
                                                                        {cells.map((cell, cellIndex) => {
                                                                            const Tag = isHeader ? 'th' : 'td';
                                                                            return (
                                                                                <Tag
                                                                                    key={cellIndex}
                                                                                    className={`px-4 py-2 text-sm ${isHeader
                                                                                        ? 'font-medium text-gray-900'
                                                                                        : 'text-gray-700'
                                                                                        }`}
                                                                                >
                                                                                    {parseMarkdown(cell.trim())}
                                                                                </Tag>
                                                                            );
                                                                        })}
                                                                    </tr>
                                                                );
                                                            }).filter(Boolean)}
                                                        </table>
                                                    </div>
                                                );
                                                inTable = false;
                                                tableLines = [];
                                            }

                                            // Regular line processing
                                            if (line.includes('Result:')) {
                                                const parts = line.split('Result:');
                                                elements.push(
                                                    <p key={i}>
                                                        {parseMarkdown(parts[0])}
                                                        <span className="font-medium text-gray-800">Result:</span>
                                                        {parseMarkdown(parts[1])}
                                                    </p>
                                                );
                                            } else if (line.trim() !== '') {
                                                elements.push(renderLineWithMarkdown(line, i));
                                            } else {
                                                // Empty line for spacing
                                                elements.push(<div key={i} className="h-2"></div>);
                                            }
                                        }
                                    }

                                    // Handle any remaining table lines
                                    if (inTable && tableLines.length > 0) {
                                        elements.push(
                                            <div key="table-final" className="overflow-x-auto my-2">
                                                <table className="min-w-full divide-y divide-gray-200 border border-gray-200">
                                                    {tableLines.map((tableLine, tableIndex) => {
                                                        const cells = tableLine.split('|').filter(cell => cell.trim() !== '');
                                                        const isHeader = tableIndex === 0;
                                                        const isSeparator = cells.every(cell => /^[-\s]+$/.test(cell));

                                                        if (isSeparator) return null;

                                                        return (
                                                            <tr key={tableIndex} className={isHeader ? 'bg-gray-50' : ''}>
                                                                {cells.map((cell, cellIndex) => {
                                                                    const Tag = isHeader ? 'th' : 'td';
                                                                    return (
                                                                        <Tag
                                                                            key={cellIndex}
                                                                            className={`px-4 py-2 text-sm ${isHeader
                                                                                ? 'font-medium text-gray-900'
                                                                                : 'text-gray-700'
                                                                                }`}
                                                                        >
                                                                            {parseMarkdown(cell.trim())}
                                                                        </Tag>
                                                                    );
                                                                })}
                                                            </tr>
                                                        );
                                                    }).filter(Boolean)}
                                                </table>
                                            </div>
                                        );
                                    }

                                    // Handle any remaining code block
                                    if (inCodeBlock && codeBlockLines.length > 0) {
                                        elements.push(
                                            <div key="code-final" className="my-3">
                                                <div className="bg-gray-900 rounded-lg overflow-hidden">
                                                    {codeBlockLanguage && (
                                                        <div className="bg-gray-800 px-4 py-2 text-xs text-gray-300 font-mono">
                                                            {codeBlockLanguage}
                                                        </div>
                                                    )}
                                                    <pre className="bg-gray-100 p-4 text-sm font-mono text-gray-800 overflow-x-auto">
                                                        <code>{codeBlockLines.join('\n')}</code>
                                                    </pre>
                                                </div>
                                            </div>
                                        );
                                    }

                                    return elements;
                                })()}
                            </div>
                        </div>
                        {message.sql &&
                            !message.sql.toLowerCase().includes('no sql query is needed') &&
                            message.sql.trim() !== '' &&
                            <SQLCodeBlock sql={message.sql} />}
                        {message.results &&
                            (Array.isArray(message.results) ? message.results.length > 0 : true) &&
                            !message.answer.includes('|') && // Don't show results table if answer already contains a table
                            <ResultsTable results={message.results} />}

                        {/* Truncation notice (FE: results polish) */}
                        {!message.isTyping && message.results_truncated && (
                            <div className="mt-3 flex items-center text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                                <i className="fas fa-info-circle mr-2 text-amber-500"></i>
                                <span>
                                    Results truncated
                                    {typeof message.row_cap === 'number' ? ` — only the first ${message.row_cap} rows were kept` : ''}.
                                    Download the CSV to save what is shown.
                                </span>
                            </div>
                        )}

                        {/* Follow-up Questions - only for latest message */}
                        {onFollowUpClick && message.follow_up_questions && message.follow_up_questions.length > 0 && (
                            <div className="mt-4 pt-4 border-t border-gray-100">
                                <p className="font-medium text-gray-700 mb-3 text-sm flex items-center">
                                    <i className="fas fa-lightbulb text-yellow-500 mr-2"></i>
                                    Follow-up Questions:
                                </p>
                                <div className="space-y-2">
                                    {message.follow_up_questions.map((question, index) => (
                                        <button
                                            key={index}
                                            onClick={() => onFollowUpClick(question)}
                                            className="block w-full text-left p-3 bg-gradient-to-r from-blue-50 to-indigo-50 hover:from-blue-100 hover:to-indigo-100 rounded-lg border border-blue-200 hover:border-blue-300 transition-all duration-200 text-sm text-gray-700 hover:text-blue-800 group"
                                        >
                                            <div className="flex items-start">
                                                <i className="fas fa-question-circle text-blue-500 mr-2 mt-0.5 text-xs group-hover:text-blue-600"></i>
                                                <span className="leading-relaxed">{question}</span>
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
};

export default ChatMessage;