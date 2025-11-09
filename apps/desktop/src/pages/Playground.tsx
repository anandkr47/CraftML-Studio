/**
 * Playground Page
 * Interactive interface for testing trained models locally
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Bot,
  User,
  Loader2,
  Settings as SettingsIcon,
  Trash2,
  Play,
  Square,
} from 'lucide-react';
import { Container } from '../components/ui/Container';
import { Card, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { HStack, VStack } from '../components/ui/Stack';
import { useNotificationStore } from '../store/notificationStore';

// Add fadeIn animation styles
const fadeInStyles = `
  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
`;

// Inject styles
if (typeof document !== 'undefined') {
  const styleSheet = document.createElement('style');
  styleSheet.textContent = fadeInStyles;
  document.head.appendChild(styleSheet);
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface Model {
  model_id: string;
  name: string;
  path: string;
  size_mb: number;
  type: 'full' | 'lora';
  is_loaded: boolean;
}

interface GenerationParams {
  max_length: number;
  temperature: number;
  top_p: number;
  top_k: number;
  repetition_penalty: number;
}

const Playground: React.FC = () => {
  const [models, setModels] = useState<Model[]>([]);
  const [selectedModel, setSelectedModel] = useState<Model | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [params, setParams] = useState<GenerationParams>({
    max_length: 150,
    temperature: 0.7,
    top_p: 0.9,
    top_k: 50,
    repetition_penalty: 1.1,
  });
  
  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { success: showSuccess, error: showError, info: showInfo } = useNotificationStore();

  useEffect(() => {
    loadModels();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadModels = async () => {
    try {
      const response = await fetch('http://127.0.0.1:5000/api/playground/models');
      const data = await response.json();
      setModels(data.models || []);
    } catch (error) {
      console.error('Failed to load models:', error);
      showError('Failed to load models');
    }
  };

  const loadModel = async (model: Model) => {
    try {
      showInfo('Loading model...');
      const response = await fetch(
        `http://127.0.0.1:5000/api/playground/load/${model.model_id}`,
        { method: 'POST' }
      );

      if (!response.ok) {
        throw new Error('Failed to load model');
      }

      setSelectedModel(model);
      showSuccess(`Model ${model.name} loaded successfully`);
      await loadModels(); // Refresh to update is_loaded status
    } catch (error: any) {
      console.error('Failed to load model:', error);
      showError(error.message || 'Failed to load model');
    }
  };

  const unloadModel = async (model: Model) => {
    try {
      const response = await fetch(
        `http://127.0.0.1:5000/api/playground/unload/${model.model_id}`,
        { method: 'POST' }
      );

      if (!response.ok) {
        throw new Error('Failed to unload model');
      }

      if (selectedModel?.model_id === model.model_id) {
        setSelectedModel(null);
      }
      showSuccess(`Model ${model.name} unloaded`);
      await loadModels();
    } catch (error: any) {
      console.error('Failed to unload model:', error);
      showError(error.message || 'Failed to unload model');
    }
  };

  const handleSend = async () => {
    if (!input.trim() || !selectedModel || isGenerating) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsGenerating(true);

    // Add a temporary "thinking" message
    const thinkingId = 'thinking-' + Date.now();
    const thinkingMessage: Message = {
      id: thinkingId,
      role: 'assistant',
      content: '...',
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, thinkingMessage]);

    try {
      const response = await fetch('http://127.0.0.1:5000/api/playground/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_path: selectedModel.path,
          prompt: userMessage.content,
          ...params,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Generation failed');
      }

      const data = await response.json();

      // Remove thinking message and add actual response
      setMessages((prev) => {
        const filtered = prev.filter(m => m.id !== thinkingId);
        return [
          ...filtered,
          {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: data.generated_text || data.text || 'No response generated',
            timestamp: new Date(),
          },
        ];
      });
    } catch (error: any) {
      console.error('Generation error:', error);
      // Remove thinking message
      setMessages((prev) => prev.filter(m => m.id !== thinkingId));
      showError(error.message || 'Failed to generate response');
    } finally {
      setIsGenerating(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
    showInfo('Chat cleared');
  };

  return (
    <div className="min-h-screen bg-neutral-50 dark:bg-neutral-900">
      <Container maxWidth="full" className="py-6">
        <VStack spacing={6}>
          {/* Header */}
          <div>
            <h1 className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
              Model Playground
            </h1>
            <p className="text-neutral-600 dark:text-neutral-400 mt-1">
              Test and interact with your trained models locally
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Sidebar - Model Selection */}
            <div className="lg:col-span-1">
              <Card>
                <CardContent className="pt-6">
                  <h3 className="font-semibold text-neutral-900 dark:text-neutral-100 mb-4">
                    Available Models
                  </h3>
                  
                  <VStack spacing={2}>
                    {models.length === 0 ? (
                      <div className="text-center py-8 text-neutral-500 dark:text-neutral-400 text-sm">
                        <Bot className="w-12 h-12 mx-auto mb-3 opacity-50" />
                        <p>No trained models found</p>
                        <p className="mt-1 text-xs">Train a model first</p>
                      </div>
                    ) : (
                      models.map((model) => (
                        <div
                          key={model.model_id}
                          className={`p-3 rounded-lg border-2 transition-all ${
                            selectedModel?.model_id === model.model_id
                              ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                              : 'border-neutral-200 dark:border-neutral-700'
                          }`}
                        >
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex-1">
                              <h4 className="font-medium text-sm text-neutral-900 dark:text-neutral-100">
                                {model.name}
                              </h4>
                              <HStack spacing={2} className="mt-1">
                                <p className="text-xs text-neutral-500 dark:text-neutral-400">
                                  {model.size_mb.toFixed(1)} MB
                                </p>
                                <Badge 
                                  variant={model.type === 'lora' ? 'info' : 'primary'} 
                                  size="sm"
                                >
                                  {model.type === 'lora' ? 'LoRA' : 'Full'}
                                </Badge>
                              </HStack>
                            </div>
                            {model.is_loaded && (
                              <Badge variant="success" size="sm">
                                Loaded
                              </Badge>
                            )}
                          </div>
                          
                          <HStack spacing={1}>
                            {!model.is_loaded ? (
                              <Button
                                size="sm"
                                variant="primary"
                                onClick={() => loadModel(model)}
                                className="flex-1"
                              >
                                <Play className="w-3 h-3 mr-1" />
                                Load
                              </Button>
                            ) : (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => unloadModel(model)}
                                className="flex-1"
                              >
                                <Square className="w-3 h-3 mr-1" />
                                Unload
                              </Button>
                            )}
                          </HStack>
                        </div>
                      ))
                    )}
                  </VStack>

                  {/* Generation Settings */}
                  <div className="mt-6">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowSettings(!showSettings)}
                      className="w-full"
                    >
                      <SettingsIcon className="w-4 h-4 mr-2" />
                      Generation Settings
                    </Button>

                    {showSettings && (
                      <VStack spacing={3} className="mt-4">
                        <div>
                          <label className="text-xs font-medium text-neutral-700 dark:text-neutral-300">
                            Max Length: {params.max_length}
                          </label>
                          <input
                            type="range"
                            min="50"
                            max="1024"
                            step="50"
                            value={params.max_length}
                            onChange={(e) =>
                              setParams({ ...params, max_length: parseInt(e.target.value) })
                            }
                            className="w-full"
                          />
                        </div>

                        <div>
                          <label className="text-xs font-medium text-neutral-700 dark:text-neutral-300">
                            Temperature: {params.temperature.toFixed(2)}
                          </label>
                          <input
                            type="range"
                            min="0"
                            max="2"
                            step="0.1"
                            value={params.temperature}
                            onChange={(e) =>
                              setParams({ ...params, temperature: parseFloat(e.target.value) })
                            }
                            className="w-full"
                          />
                        </div>

                        <div>
                          <label className="text-xs font-medium text-neutral-700 dark:text-neutral-300">
                            Top P: {params.top_p.toFixed(2)}
                          </label>
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.05"
                            value={params.top_p}
                            onChange={(e) =>
                              setParams({ ...params, top_p: parseFloat(e.target.value) })
                            }
                            className="w-full"
                          />
                        </div>
                      </VStack>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Main Chat Area */}
            <div className="lg:col-span-3">
              <Card className="h-[calc(100vh-200px)] flex flex-col">
                <CardContent className="pt-6 flex-1 flex flex-col">
                  {!selectedModel ? (
                    <div className="flex-1 flex items-center justify-center text-neutral-500 dark:text-neutral-400">
                      <VStack spacing={3} align="center">
                        <Bot className="w-16 h-16 opacity-50" />
                        <p className="text-lg font-medium">No Model Selected</p>
                        <p className="text-sm">Select and load a model to start chatting</p>
                      </VStack>
                    </div>
                  ) : (
                    <>
                      {/* Chat Header */}
                      <div className="flex items-center justify-between pb-4 border-b border-neutral-200 dark:border-neutral-700">
                        <HStack spacing={3} align="center">
                          <div className="p-2 bg-brand-100 dark:bg-brand-900/30 rounded-lg">
                            <Bot className="w-5 h-5 text-brand-600 dark:text-brand-400" />
                          </div>
                          <div>
                            <h3 className="font-semibold text-neutral-900 dark:text-neutral-100">
                              {selectedModel.name}
                            </h3>
                            <p className="text-xs text-neutral-500 dark:text-neutral-400">
                              Ready to chat
                            </p>
                          </div>
                        </HStack>

                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={clearChat}
                          disabled={messages.length === 0}
                        >
                          <Trash2 className="w-4 h-4 mr-2" />
                          Clear
                        </Button>
                      </div>

                      {/* Messages */}
                      <div className="flex-1 overflow-y-auto py-4 px-2 space-y-4 scroll-smooth">
                        {messages.length === 0 ? (
                          <div className="flex items-center justify-center h-full text-neutral-500 dark:text-neutral-400">
                            <VStack spacing={2} align="center">
                              <p>Start a conversation</p>
                              <p className="text-xs">Type a message below to begin</p>
                            </VStack>
                          </div>
                        ) : (
                          messages.map((message) => (
                            <div
                              key={message.id}
                              className={`flex gap-3 animate-fadeIn ${
                                message.role === 'user' ? 'justify-end' : 'justify-start'
                              }`}
                              style={{
                                animation: 'fadeIn 0.3s ease-in-out',
                              }}
                            >
                              {message.role === 'assistant' && (
                                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-brand-100 dark:bg-brand-900/30 flex items-center justify-center">
                                  <Bot className="w-5 h-5 text-brand-600 dark:text-brand-400" />
                                </div>
                              )}

                              <div
                                className={`max-w-[70%] rounded-lg px-4 py-3 ${
                                  message.role === 'user'
                                    ? 'bg-brand-500 text-white'
                                    : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100'
                                }`}
                              >
                                {message.content === '...' && message.role === 'assistant' ? (
                                  <div className="flex items-center gap-2">
                                    <Loader2 className="w-4 h-4 animate-spin text-brand-600 dark:text-brand-400" />
                                    <span className="text-sm italic text-neutral-600 dark:text-neutral-400">
                                      Model is thinking...
                                    </span>
                                  </div>
                                ) : (
                                  <>
                                    <p className="text-sm whitespace-pre-wrap break-words">{message.content}</p>
                                    <p
                                      className={`text-xs mt-2 ${
                                        message.role === 'user'
                                          ? 'text-brand-100'
                                          : 'text-neutral-500 dark:text-neutral-400'
                                      }`}
                                    >
                                      {message.timestamp.toLocaleTimeString()}
                                    </p>
                                  </>
                                )}
                              </div>

                              {message.role === 'user' && (
                                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-neutral-200 dark:bg-neutral-700 flex items-center justify-center">
                                  <User className="w-5 h-5 text-neutral-600 dark:text-neutral-400" />
                                </div>
                              )}
                            </div>
                          ))
                        )}
                        <div ref={messagesEndRef} />
                      </div>

                      {/* Input */}
                      <div className="pt-4 border-t border-neutral-200 dark:border-neutral-700">
                        <div className="flex gap-2 items-end">
                          <textarea
                            placeholder="Type your message... (Press Enter to send, Shift+Enter for new line)"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                handleSend();
                              }
                            }}
                            disabled={isGenerating}
                            rows={1}
                            className="flex-1 px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 resize-none focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:opacity-50 disabled:cursor-not-allowed min-h-[42px] max-h-[120px]"
                            style={{ 
                              height: 'auto',
                              overflowY: input.split('\n').length > 3 ? 'auto' : 'hidden'
                            }}
                          />
                          <Button
                            onClick={handleSend}
                            disabled={!input.trim() || isGenerating}
                            variant="primary"
                            className="h-[42px] px-4"
                          >
                            {isGenerating ? (
                              <Loader2 className="w-5 h-5 animate-spin" />
                            ) : (
                              <Send className="w-5 h-5" />
                            )}
                          </Button>
                        </div>
                        {isGenerating && (
                          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-2 flex items-center gap-1">
                            <Loader2 className="w-3 h-3 animate-spin" />
                            Generating response...
                          </p>
                        )}
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        </VStack>
      </Container>
    </div>
  );
};

export default Playground;

