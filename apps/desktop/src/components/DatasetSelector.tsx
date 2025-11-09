/**
 * Dataset Selector Component
 * Comprehensive dataset selection with preview, upload, and management
 */

import React, { useState, useEffect } from 'react';
import {
  Database,
  Upload,
  FileText,
  Eye,
  CheckCircle2,
  AlertCircle,
  Download,
  Plus,
  RefreshCw,
  Search,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/Card';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Badge } from './ui/Badge';
import { HStack, VStack } from './ui/Stack';
import { Modal } from './ui/Modal';
import { Textarea } from './ui/Textarea';
import { useNotificationStore } from '../store/notificationStore';

interface Dataset {
  dataset_id?: string;
  id?: number;
  name: string;
  description?: string;
  format: string;
  size_mb: number;
  num_samples?: number;
  num_examples?: number;
  created_at: string;
  file_path?: string;
  quality_score?: number;
}

interface ModelOption {
  type: 'pretrained' | 'scratch';
}

interface DatasetSelectorProps {
  selectedModel: ModelOption | null;
  selectedDataset: Dataset | null;
  onDatasetSelect: (dataset: Dataset | null) => void;
}

const CURATED_DATASETS = [
  {
    id: 'alpaca',
    name: 'Alpaca Instruction Dataset',
    description: '52K instruction-following examples for general fine-tuning',
    format: 'jsonl',
    examples: 52000,
    category: 'instruction',
  },
  {
    id: 'dolly',
    name: 'Dolly 15K',
    description: 'High-quality instruction dataset from Databricks',
    format: 'jsonl',
    examples: 15000,
    category: 'instruction',
  },
  {
    id: 'openassistant',
    name: 'OpenAssistant Conversations',
    description: 'Human-generated assistant conversations',
    format: 'jsonl',
    examples: 88000,
    category: 'conversation',
  },
];

export const DatasetSelector: React.FC<DatasetSelectorProps> = ({
  selectedModel,
  selectedDataset,
  onDatasetSelect,
}) => {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [previewData, setPreviewData] = useState<any[]>([]);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadName, setUploadName] = useState('');
  const [uploadDescription, setUploadDescription] = useState('');

  const { success: showSuccess, error: showError, info: showInfo } = useNotificationStore();

  const isFromScratch = selectedModel?.type === 'scratch';

  useEffect(() => {
    loadDatasets();
  }, []);

  const loadDatasets = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://127.0.0.1:5000/api/dataset/list');
      if (response.ok) {
        const data = await response.json();
        // Add file_path to each dataset
        const datasetsWithPath = (data.datasets || []).map((ds: any) => ({
          ...ds,
          id: ds.dataset_id || ds.id,
          file_path: ds.file_path || `resources/datasets/${ds.name}`,
          num_examples: ds.num_samples || ds.num_examples,
        }));
        setDatasets(datasetsWithPath);
      }
    } catch (error) {
      console.error('Error loading datasets:', error);
    } finally {
      setLoading(false);
    }
  };

  const handlePreview = async (_dataset: Dataset) => {
    try {
      // Mock preview - in production, fetch from API
      const mockData = [
        { instruction: 'What is machine learning?', output: 'Machine learning is...' },
        { instruction: 'Explain neural networks', output: 'Neural networks are...' },
        { instruction: 'What is deep learning?', output: 'Deep learning is...' },
      ];
      setPreviewData(mockData);
      setShowPreviewModal(true);
    } catch (error) {
      showError('Failed to load dataset preview');
    }
  };

  const handleUpload = async () => {
    if (!uploadFile) {
      showError('Please select a file to upload');
      return;
    }

    if (!uploadName.trim()) {
      showError('Please enter a dataset name');
      return;
    }

    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('name', uploadName);
      formData.append('description', uploadDescription);

      const response = await fetch('http://127.0.0.1:5000/api/dataset-upload/upload', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        showSuccess('Dataset uploaded successfully!');
        setShowUploadModal(false);
        setUploadFile(null);
        setUploadName('');
        setUploadDescription('');
        await loadDatasets();
      } else {
        const error = await response.json();
        showError(error.detail || 'Upload failed');
      }
    } catch (error) {
      showError('Failed to upload dataset');
      console.error('Upload error:', error);
    }
  };

  const handleDownloadCurated = async (curatedId: string) => {
    showInfo(`Downloading ${curatedId} dataset...`);
    // In production, implement actual download
    setTimeout(() => {
      showSuccess(`${curatedId} dataset downloaded!`);
      loadDatasets();
    }, 2000);
  };

  const filteredDatasets = datasets.filter((d) =>
    d.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    d.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <Card>
      <CardHeader>
        <HStack justify="between" align="start">
          <div>
            <CardTitle>
              <Database className="w-5 h-5 inline mr-2" />
              Dataset Selection
            </CardTitle>
            <CardDescription>
              {isFromScratch
                ? 'Import or upload your custom dataset for training from scratch'
                : 'Choose a curated instruction dataset or upload your own'}
            </CardDescription>
          </div>
          <HStack spacing={2}>
            <Button
              variant="ghost"
              size="sm"
              onClick={loadDatasets}
              leftIcon={<RefreshCw className="w-4 h-4" />}
            >
              Refresh
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setShowUploadModal(true)}
              leftIcon={<Upload className="w-4 h-4" />}
            >
              Upload Dataset
            </Button>
          </HStack>
        </HStack>
      </CardHeader>

      <CardContent>
        <VStack spacing={6}>
          {/* Search */}
          <Input
            type="text"
            placeholder="Search datasets..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            leftIcon={<Search className="w-4 h-4" />}
          />

          {/* Curated Datasets (for fine-tuning) */}
          {!isFromScratch && (
            <div>
              <h4 className="font-semibold text-neutral-900 dark:text-neutral-100 mb-3">
                Curated Instruction Datasets
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {CURATED_DATASETS.map((curated) => (
                  <button
                    key={curated.id}
                    onClick={() => handleDownloadCurated(curated.id)}
                    className="p-4 rounded-lg border-2 border-neutral-200 dark:border-neutral-700 hover:border-brand-300 dark:hover:border-brand-700 text-left transition-all"
                  >
                    <HStack justify="between" align="start">
                      <div className="flex-1">
                        <h5 className="font-semibold text-neutral-900 dark:text-neutral-100">
                          {curated.name}
                        </h5>
                        <p className="text-sm text-neutral-600 dark:text-neutral-400 mt-1">
                          {curated.description}
                        </p>
                        <HStack spacing={2} className="mt-3">
                          <Badge variant="default" size="sm">
                            {curated.examples.toLocaleString()} examples
                          </Badge>
                          <Badge variant="info" size="sm">
                            {curated.category}
                          </Badge>
                        </HStack>
                      </div>
                      <Download className="w-5 h-5 text-brand-600 dark:text-brand-400" />
                    </HStack>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* User Datasets */}
          <div>
            <h4 className="font-semibold text-neutral-900 dark:text-neutral-100 mb-3">
              {isFromScratch ? 'Your Datasets' : 'Custom Datasets'}
            </h4>

            {loading ? (
              <div className="text-center py-8 text-neutral-500">Loading datasets...</div>
            ) : filteredDatasets.length === 0 ? (
              <div className="text-center py-12 border-2 border-dashed border-neutral-300 dark:border-neutral-700 rounded-lg">
                <Database className="w-12 h-12 text-neutral-400 mx-auto mb-4" />
                <p className="text-neutral-600 dark:text-neutral-400 mb-4">
                  No datasets found. Upload one to get started!
                </p>
                <Button
                  variant="primary"
                  onClick={() => setShowUploadModal(true)}
                  leftIcon={<Plus className="w-4 h-4" />}
                >
                  Upload Dataset
                </Button>
              </div>
            ) : (
              <div className="space-y-2">
                {filteredDatasets.map((dataset) => {
                  const isSelected = selectedDataset?.id === dataset.id;

                  return (
                    <button
                      key={dataset.id}
                      onClick={() => onDatasetSelect(isSelected ? null : dataset)}
                      className={`w-full p-4 rounded-lg border-2 text-left transition-all ${
                        isSelected
                          ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                          : 'border-neutral-200 dark:border-neutral-700 hover:border-brand-300 dark:hover:border-brand-700'
                      }`}
                    >
                      <HStack justify="between" align="start">
                        <div className="flex-1">
                          <HStack spacing={2} align="center" className="mb-2">
                            <h5 className="font-semibold text-neutral-900 dark:text-neutral-100">
                              {dataset.name}
                            </h5>
                            {isSelected && (
                              <CheckCircle2 className="w-4 h-4 text-brand-600" />
                            )}
                          </HStack>
                          {dataset.description && (
                            <p className="text-sm text-neutral-600 dark:text-neutral-400 mb-2">
                              {dataset.description}
                            </p>
                          )}
                          <HStack spacing={2}>
                            <Badge variant="default" size="sm">
                              {dataset.format.toUpperCase()}
                            </Badge>
                            <Badge variant="default" size="sm">
                              {dataset.size_mb.toFixed(1)} MB
                            </Badge>
                            {dataset.num_examples && (
                              <Badge variant="info" size="sm">
                                {dataset.num_examples.toLocaleString()} examples
                              </Badge>
                            )}
                            {dataset.quality_score && (
                              <Badge
                                variant={
                                  dataset.quality_score > 0.8
                                    ? 'success'
                                    : dataset.quality_score > 0.6
                                    ? 'warning'
                                    : 'error'
                                }
                                size="sm"
                              >
                                Quality: {(dataset.quality_score * 100).toFixed(0)}%
                              </Badge>
                            )}
                          </HStack>
                        </div>
                        <HStack spacing={2}>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              handlePreview(dataset);
                            }}
                            leftIcon={<Eye className="w-4 h-4" />}
                          />
                        </HStack>
                      </HStack>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Selected Dataset Info */}
          {selectedDataset && (
            <div className="bg-success-50 dark:bg-success-900/20 border border-success-200 dark:border-success-800 rounded-lg p-4">
              <HStack spacing={3} align="start">
                <CheckCircle2 className="w-5 h-5 text-success-600 dark:text-success-400 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="font-medium text-success-900 dark:text-success-100">
                    Dataset Selected: {selectedDataset.name}
                  </p>
                  <p className="text-sm text-success-700 dark:text-success-300 mt-1">
                    Path: {selectedDataset.file_path}
                  </p>
                  <p className="text-xs text-success-600 dark:text-success-400 mt-2">
                    Auto-split: 80% train, 20% validation • Format: {selectedDataset.format}
                  </p>
                </div>
              </HStack>
            </div>
          )}
        </VStack>
      </CardContent>

      {/* Upload Modal */}
      <Modal
        isOpen={showUploadModal}
        onClose={() => setShowUploadModal(false)}
        title="Upload Dataset"
        size="lg"
      >
        <VStack spacing={5}>
          {/* Info Banner */}
          <div className="bg-gradient-to-r from-brand-50 to-brand-100 dark:from-brand-900/20 dark:to-brand-800/20 border border-brand-200 dark:border-brand-700 rounded-lg p-4">
            <HStack spacing={3} align="start">
              <div className="p-2 bg-brand-100 dark:bg-brand-900/40 rounded-lg">
                <Upload className="w-5 h-5 text-brand-600 dark:text-brand-400" />
              </div>
              <div className="flex-1">
                <h4 className="font-semibold text-brand-900 dark:text-brand-100 mb-1">
                  Upload Your Training Dataset
                </h4>
                <p className="text-sm text-brand-700 dark:text-brand-300">
                  Upload instruction-output pairs for fine-tuning or raw text for training from scratch
                </p>
              </div>
            </HStack>
          </div>

          {/* Dataset Name */}
          <div>
            <label className="block text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-2">
              Dataset Name <span className="text-danger-500">*</span>
            </label>
            <Input
              type="text"
              value={uploadName}
              onChange={(e) => setUploadName(e.target.value)}
              placeholder="e.g., Customer Support QA Dataset"
              className="w-full"
            />
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
              Choose a descriptive name to identify your dataset
            </p>
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-2">
              Description (Optional)
            </label>
            <Textarea
              value={uploadDescription}
              onChange={(e) => setUploadDescription(e.target.value)}
              placeholder="Describe the content, use case, or source of this dataset..."
              rows={3}
              className="w-full"
            />
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
              Add context to help you remember this dataset later
            </p>
          </div>

          {/* File Upload */}
          <div>
            <label className="block text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-2">
              Dataset File <span className="text-danger-500">*</span>
            </label>
            <div className="relative">
              <label
                className={`flex flex-col items-center justify-center w-full h-32 border-2 border-dashed rounded-lg cursor-pointer transition-all ${
                  uploadFile
                    ? 'border-success-400 bg-success-50 dark:bg-success-900/20'
                    : 'border-neutral-300 dark:border-neutral-700 hover:border-brand-400 dark:hover:border-brand-600 bg-neutral-50 dark:bg-neutral-800/50 hover:bg-brand-50 dark:hover:bg-brand-900/20'
                }`}
              >
                <div className="flex flex-col items-center justify-center pt-5 pb-6">
                  {uploadFile ? (
                    <>
                      <CheckCircle2 className="w-10 h-10 text-success-500 mb-3" />
                      <p className="text-sm font-medium text-success-700 dark:text-success-400">
                        {uploadFile.name}
                      </p>
                      <p className="text-xs text-success-600 dark:text-success-500 mt-1">
                        {(uploadFile.size / 1024 / 1024).toFixed(2)} MB • {uploadFile.type || 'File'}
                      </p>
                      <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-2">
                        Click to change file
                      </p>
                    </>
                  ) : (
                    <>
                      <FileText className="w-10 h-10 text-neutral-400 mb-3" />
                      <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
                        Click to upload or drag and drop
                      </p>
                      <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                        JSON, JSONL, CSV, or TXT
                      </p>
                    </>
                  )}
                </div>
                <input
                  type="file"
                  accept=".json,.jsonl,.csv,.txt"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="hidden"
                />
              </label>
            </div>
          </div>

          {/* Format Guide */}
          <div className="bg-neutral-50 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-neutral-600 dark:text-neutral-400 flex-shrink-0 mt-0.5" />
              <div>
                <h5 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-2">
                  Supported Formats
                </h5>
                <div className="space-y-2 text-xs text-neutral-700 dark:text-neutral-300">
                  <div className="flex gap-2">
                    <Badge variant="default" size="sm">JSON</Badge>
                    <code className="flex-1 bg-neutral-100 dark:bg-neutral-900 px-2 py-1 rounded">
                      [{"{"}"instruction": "...", "output": "..."{"}"}, ...]
                    </code>
                  </div>
                  <div className="flex gap-2">
                    <Badge variant="default" size="sm">JSONL</Badge>
                    <code className="flex-1 bg-neutral-100 dark:bg-neutral-900 px-2 py-1 rounded">
                      {"{"}"instruction": "...", "output": "..."{"}"}
                    </code>
                  </div>
                  <div className="flex gap-2">
                    <Badge variant="default" size="sm">CSV</Badge>
                    <code className="flex-1 bg-neutral-100 dark:bg-neutral-900 px-2 py-1 rounded">
                      instruction,output
                    </code>
                  </div>
                  <div className="flex gap-2">
                    <Badge variant="default" size="sm">TXT</Badge>
                    <span className="flex-1 text-neutral-600 dark:text-neutral-400">
                      Plain text (for training from scratch)
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex justify-between items-center pt-2 border-t border-neutral-200 dark:border-neutral-700">
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              {uploadFile && uploadName.trim() ? (
                <span className="text-success-600 dark:text-success-400 font-medium">
                  ✓ Ready to upload
                </span>
              ) : (
                <span>Please fill in required fields</span>
              )}
            </p>
            <HStack spacing={3}>
              <Button 
                variant="ghost" 
                onClick={() => {
                  setShowUploadModal(false);
                  setUploadFile(null);
                  setUploadName('');
                  setUploadDescription('');
                }}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleUpload}
                disabled={!uploadFile || !uploadName.trim()}
              >
                <Upload className="w-4 h-4 mr-2" />
                Upload Dataset
              </Button>
            </HStack>
          </div>
        </VStack>
      </Modal>

      {/* Preview Modal */}
      <Modal
        isOpen={showPreviewModal}
        onClose={() => setShowPreviewModal(false)}
        title="Dataset Preview"
        size="lg"
      >
        <VStack spacing={4}>
          <p className="text-sm text-neutral-600 dark:text-neutral-400">
            Showing first 10 examples from dataset
          </p>

          <div className="space-y-3 max-h-96 overflow-y-auto">
            {previewData.map((item, index) => (
              <div
                key={index}
                className="p-4 bg-neutral-50 dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700"
              >
                <div className="mb-2">
                  <Badge variant="default" size="sm">
                    Example {index + 1}
                  </Badge>
                </div>
                <div className="space-y-2">
                  <div>
                    <p className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase">
                      Instruction
                    </p>
                    <p className="text-sm text-neutral-900 dark:text-neutral-100">
                      {item.instruction}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase">
                      Output
                    </p>
                    <p className="text-sm text-neutral-900 dark:text-neutral-100">
                      {item.output}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </VStack>
      </Modal>
    </Card>
  );
};

export default DatasetSelector;

