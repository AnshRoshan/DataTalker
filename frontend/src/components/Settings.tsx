import React, { useState } from 'react';

interface SettingsProps {
    isOpen: boolean;
    onClose: () => void;
}

interface SettingsState {
    apiUrl: string;
    apiKey: string;
}

const Settings: React.FC<SettingsProps> = ({ isOpen, onClose }) => {
    const [settings, setSettings] = useState<SettingsState>({
        apiUrl: localStorage.getItem('apiUrl') || 'http://127.0.0.1:8000',
        apiKey: localStorage.getItem('apiKey') || '',
    });

    const [testingConnection, setTestingConnection] = useState(false);
    const [connectionStatus, setConnectionStatus] = useState<'idle' | 'success' | 'error'>('idle');

    const handleSave = () => {
        Object.entries(settings).forEach(([key, value]) => {
            localStorage.setItem(key, value.toString());
        });
        onClose();
        showNotification('Settings saved successfully!');
    };

    const testConnection = async () => {
        setTestingConnection(true);
        setConnectionStatus('idle');

        try {
            const response = await fetch(`${settings.apiUrl}/health`, {
                headers: settings.apiKey ? { 'Authorization': `Bearer ${settings.apiKey}` } : {}
            });

            if (response.ok) {
                setConnectionStatus('success');
            } else {
                setConnectionStatus('error');
            }
        } catch (error) {
            setConnectionStatus('error');
        } finally {
            setTestingConnection(false);
        }
    };

    const showNotification = (message: string) => {
        const notification = document.createElement('div');
        notification.className = 'fixed bottom-4 right-4 bg-green-500 text-white px-4 py-2 rounded-lg shadow-lg z-50';
        notification.textContent = message;
        document.body.appendChild(notification);
        setTimeout(() => notification.remove(), 3000);
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 overflow-y-auto">
            <div className="flex items-center justify-center min-h-screen px-4">
                <div className="fixed inset-0 bg-black opacity-50" onClick={onClose}></div>

                <div className="relative bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden">
                    <div className="sticky top-0 bg-white border-b px-6 py-4">
                        <div className="flex items-center justify-between">
                            <h2 className="text-2xl font-bold text-gray-800">Settings</h2>
                            <button
                                onClick={onClose}
                                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                            >
                                <i className="fas fa-times text-gray-600"></i>
                            </button>
                        </div>
                    </div>

                    <div className="px-6 py-4 overflow-y-auto max-h-[calc(90vh-8rem)]">
                        {/* API Configuration */}
                        <div className="mb-6">
                            <h3 className="text-lg font-semibold text-gray-700 mb-4 flex items-center">
                                <i className="fas fa-server mr-2 text-blue-600"></i>
                                API Configuration
                            </h3>

                            <div className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        FastAPI URL
                                    </label>
                                    <div className="flex space-x-2">
                                        <input
                                            type="text"
                                            value={settings.apiUrl}
                                            onChange={(e) => setSettings({ ...settings, apiUrl: e.target.value })}
                                            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                            placeholder="http://localhost:8000"
                                        />
                                        <button
                                            onClick={testConnection}
                                            disabled={testingConnection}
                                            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
                                        >
                                            {testingConnection ? (
                                                <i className="fas fa-spinner fa-spin"></i>
                                            ) : (
                                                'Test'
                                            )}
                                        </button>
                                    </div>
                                    {connectionStatus === 'success' && (
                                        <p className="mt-1 text-sm text-green-600">
                                            <i className="fas fa-check-circle mr-1"></i>
                                            Connection successful!
                                        </p>
                                    )}
                                    {connectionStatus === 'error' && (
                                        <p className="mt-1 text-sm text-red-600">
                                            <i className="fas fa-exclamation-circle mr-1"></i>
                                            Connection failed. Please check the URL.
                                        </p>
                                    )}
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        API Key (Optional)
                                    </label>
                                    <input
                                        type="password"
                                        value={settings.apiKey}
                                        onChange={(e) => setSettings({ ...settings, apiKey: e.target.value })}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                        placeholder="Enter your API key"
                                    />
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="sticky bottom-0 bg-white border-t px-6 py-4 flex justify-end space-x-4">
                        <button
                            onClick={onClose}
                            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={handleSave}
                            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                        >
                            Save
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Settings;