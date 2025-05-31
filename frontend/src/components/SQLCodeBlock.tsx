import React, { useState } from 'react';

interface SQLCodeBlockProps {
    sql: string;
}

const SQLCodeBlock: React.FC<SQLCodeBlockProps> = ({ sql }) => {
    const [copied, setCopied] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(sql);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="mt-4">
            <div className="flex items-center justify-between mb-2">
                <p className="font-semibold text-gray-700 flex items-center">
                    <i className="fas fa-code text-purple-500 mr-2"></i>
                    Generated SQL
                </p>
                <button
                    onClick={handleCopy}
                    className="text-sm px-3 py-1 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 hover:text-gray-800 transition-colors flex items-center"
                >
                    {copied ? (
                        <>
                            <i className="fas fa-check text-green-500 mr-1"></i>
                            Copied!
                        </>
                    ) : (
                        <>
                            <i className="fas fa-copy mr-1"></i>
                            Copy
                        </>
                    )}
                </button>
            </div>
            <div className="relative group">
                <div className="absolute inset-0 bg-gradient-to-r from-purple-400 to-blue-400 rounded-lg blur opacity-25 group-hover:opacity-40 transition-opacity"></div>
                <div className="relative sql-code border border-gray-700"> 
                    <pre className="text-sm">{sql}</pre>
                </div>
            </div>
        </div>
    );
};

export default SQLCodeBlock;