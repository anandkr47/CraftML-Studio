/**
 * Dataset Manager Page
 * Manage datasets with modern UI matching the design system
 */

import React, { useEffect, useState } from 'react';
import {
  Database,
  Upload,
  Download,
  Trash2,
  Edit2,
  Plus,
  FileText,
  BarChart3,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Search,
  FolderOpen,
  Info,
} from 'lucide-react';
import { Container } from '../components/ui/Container';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Badge } from '../components/ui/Badge';
import { Modal, ModalHeader, ModalBody, ModalFooter } from '../components/ui/Modal';
import { Table, Column } from '../components/ui/Table';
import { HStack, VStack } from '../components/ui/Stack';
import { Skeleton } from '../components/ui/Skeleton';
import {
  fetchDatasets,
  createDataset,
  updateDataset,
  deleteDataset,
} from '../api/dataset';
import { useNotificationStore } from '../store/notificationStore';

interface Dataset {
  id: number;
  name: string;
  file_path: string;
  token_count: number;
  quality_score: number;
  created_at: string;
}

const initialForm = {
  name: '',
  file_path: '',
  token_count: 0,
  quality_score: 0,
};

interface UploadedFile {
  file: File | null;
  name: string;
  size: number;
  type: string;
}

const DatasetManager: React.FC = () => {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [form, setForm] = useState(initialForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null);
  const [uploadMethod, setUploadMethod] = useState<'file' | 'path'>('file');
  const [uploading, setUploading] = useState(false);
  
  // Get notification methods from store
  const { success: showSuccess, error: showError, info: showInfo } = useNotificationStore();

  const loadDatasets = async () => {
    setLoading(true);
    try {
      const data = await fetchDatasets();
      setDatasets(data.datasets || []); // Extract datasets array from response
      showSuccess('Datasets loaded successfully');
    } catch (error) {
      showError('Failed to load datasets');
      console.error('Error loading datasets:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDatasets();
  }, []);

  const handleDelete = async (id: number) => {
    try {
      await deleteDataset(id);
      showSuccess('Dataset deleted successfully');
      await loadDatasets();
      setDeleteConfirmId(null);
    } catch (error) {
      showError('Failed to delete dataset');
      console.error('Error deleting dataset:', error);
    }
  };

  const handleEdit = (dataset: Dataset) => {
    setForm({
      name: dataset.name,
      file_path: dataset.file_path,
      token_count: dataset.token_count,
      quality_score: dataset.quality_score,
    });
    setEditingId(dataset.id);
    setModalOpen(true);
  };

  const handleCreate = () => {
    setForm(initialForm);
    setEditingId(null);
    setUploadedFile(null);
    setUploadMethod('file');
    setModalOpen(true);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadedFile({
        file,
        name: file.name,
        size: file.size,
        type: file.type || file.name.split('.').pop() || '',
      });
      // Auto-populate name if empty
      if (!form.name) {
        setForm({ ...form, name: file.name.replace(/\.[^/.]+$/, '') });
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingId) {
        await updateDataset(editingId, form);
        showSuccess('Dataset updated successfully');
      } else {
        await createDataset(form);
        showSuccess('Dataset created successfully');
      }
      setModalOpen(false);
      await loadDatasets();
    } catch (error) {
      showError(`Failed to ${editingId ? 'update' : 'create'} dataset`);
      console.error('Error submitting dataset:', error);
    }
  };

  // Filter datasets based on search query
  const filteredDatasets = datasets.filter((dataset) =>
    dataset.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Calculate stats
  const totalTokens = datasets.reduce((sum, d) => sum + (d.token_count || 0), 0);
  const avgQuality =
    datasets.length > 0
      ? datasets.reduce((sum, d) => sum + (d.quality_score || 0), 0) / datasets.length
      : 0;

  // Table columns
  const columns: Column<Dataset>[] = [
    {
      key: 'name',
      header: 'Dataset Name',
      render: (dataset) => (
        <HStack spacing={2}>
          <Database className="w-4 h-4 text-brand-500" />
          <span className="font-medium text-neutral-900 dark:text-neutral-100">
            {dataset.name}
          </span>
        </HStack>
      ),
    },
    {
      key: 'file_path',
      header: 'File Path',
      render: (dataset) => (
        <span className="text-sm text-neutral-600 dark:text-neutral-400 font-mono">
          {dataset.file_path}
        </span>
      ),
    },
    {
      key: 'token_count',
      header: 'Tokens',
      render: (dataset) => (
        <Badge variant="neutral" size="sm">
          {dataset.token_count?.toLocaleString() || '0'}
        </Badge>
      ),
    },
    {
      key: 'quality_score',
      header: 'Quality',
      render: (dataset) => {
        const score = dataset.quality_score || 0;
        const variant =
          score >= 80
            ? 'success'
            : score >= 50
            ? 'warning'
            : 'danger';
        return (
          <Badge variant={variant} size="sm">
            {score}%
          </Badge>
        );
      },
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (dataset) => (
        <span className="text-sm text-neutral-600 dark:text-neutral-400">
          {dataset.created_at ? new Date(dataset.created_at).toLocaleDateString() : 'N/A'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (dataset) => (
        <HStack spacing={2}>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleEdit(dataset)}
            icon={<Edit2 className="w-4 h-4" />}
          >
            Edit
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setDeleteConfirmId(dataset.id)}
            icon={<Trash2 className="w-4 h-4" />}
            className="text-danger-600 hover:text-danger-700 hover:bg-danger-50 dark:hover:bg-danger-900/20"
          >
            Delete
          </Button>
        </HStack>
      ),
    },
  ];

  return (
    <Container maxWidth="xl" className="py-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
          Dataset Manager
        </h1>
        <p className="text-neutral-600 dark:text-neutral-400 mt-1">
          Manage and organize your training datasets
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardContent className="pt-6">
            <HStack justify="between" align="start">
              <VStack spacing={1}>
                <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
                  Total Datasets
                </p>
                <div className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                  {loading ? <Skeleton className="h-10 w-16" /> : datasets.length}
                </div>
              </VStack>
              <div className="p-3 bg-brand-50 dark:bg-brand-900/20 rounded-lg">
                <Database className="w-6 h-6 text-brand-600 dark:text-brand-400" />
              </div>
            </HStack>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <HStack justify="between" align="start">
              <VStack spacing={1}>
                <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
                  Total Tokens
                </p>
                <div className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                  {loading ? (
                    <Skeleton className="h-10 w-20" />
                  ) : (
                    totalTokens.toLocaleString()
                  )}
                </div>
              </VStack>
              <div className="p-3 bg-success-50 dark:bg-success-900/20 rounded-lg">
                <FileText className="w-6 h-6 text-success-600 dark:text-success-400" />
              </div>
            </HStack>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <HStack justify="between" align="start">
              <VStack spacing={1}>
                <p className="text-sm font-medium text-neutral-600 dark:text-neutral-400">
                  Avg Quality
                </p>
                <div className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                  {loading ? <Skeleton className="h-10 w-16" /> : `${avgQuality.toFixed(0)}%`}
                </div>
              </VStack>
              <div className="p-3 bg-warning-50 dark:bg-warning-900/20 rounded-lg">
                <BarChart3 className="w-6 h-6 text-warning-600 dark:text-warning-400" />
              </div>
            </HStack>
          </CardContent>
        </Card>
      </div>

      {/* Actions & Search */}
      <Card>
        <CardContent className="pt-6">
          <HStack justify="between" className="flex-wrap gap-4">
            <div className="flex-1 min-w-[300px]">
              <Input
                placeholder="Search datasets..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                icon={<Search className="w-4 h-4" />}
              />
            </div>
            <HStack spacing={3}>
              <Button
                variant="outline"
                onClick={() => showInfo('Export feature coming soon')}
                icon={<Download className="w-4 h-4" />}
              >
                Export
              </Button>
              <Button
                variant="primary"
                onClick={handleCreate}
                icon={<Plus className="w-4 h-4" />}
              >
                Import Dataset
              </Button>
            </HStack>
          </HStack>
        </CardContent>
      </Card>

      {/* Datasets Table */}
      <Card>
        <CardHeader>
          <CardTitle>Datasets</CardTitle>
          <CardDescription>
            {filteredDatasets.length} dataset{filteredDatasets.length !== 1 ? 's' : ''}{' '}
            {searchQuery && `matching "${searchQuery}"`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <VStack spacing={4}>
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </VStack>
          ) : filteredDatasets.length === 0 ? (
            <div className="text-center py-12">
              <Database className="w-12 h-12 text-neutral-400 mx-auto mb-4" />
              <p className="text-lg font-medium text-neutral-900 dark:text-neutral-100 mb-2">
                No datasets found
              </p>
              <p className="text-neutral-600 dark:text-neutral-400 mb-6">
                {searchQuery
                  ? 'Try a different search term'
                  : 'Get started by importing your first dataset'}
              </p>
              {!searchQuery && (
                <Button variant="primary" onClick={handleCreate} icon={<Plus className="w-4 h-4" />}>
                  Import Dataset
                </Button>
              )}
            </div>
          ) : (
            <Table data={filteredDatasets} columns={columns} />
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Modal */}
      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} size="lg">
        <form onSubmit={handleSubmit}>
          <ModalHeader>
            <div>
              <h3 className="text-xl font-semibold text-neutral-900 dark:text-neutral-100">
                {editingId ? 'Edit Dataset' : 'Import Dataset'}
              </h3>
              <p className="text-sm text-neutral-600 dark:text-neutral-400 mt-1">
                {editingId ? 'Update dataset information' : 'Add a new dataset to your collection'}
              </p>
            </div>
          </ModalHeader>
          <ModalBody>
            <VStack spacing={6}>
              {/* Info Banner */}
              {!editingId && (
                <div className="bg-gradient-to-r from-brand-50 to-brand-100 dark:from-brand-900/20 dark:to-brand-800/20 border border-brand-200 dark:border-brand-700 rounded-lg p-4">
                  <HStack spacing={3} align="start">
                    <div className="p-2 bg-brand-100 dark:bg-brand-900/40 rounded-lg">
                      <Upload className="w-5 h-5 text-brand-600 dark:text-brand-400" />
                    </div>
                    <div className="flex-1">
                      <h4 className="font-semibold text-brand-900 dark:text-brand-100 mb-1">
                        Import Your Dataset
                      </h4>
                      <p className="text-sm text-brand-700 dark:text-brand-300">
                        Upload a file or specify a file path to add your dataset
                      </p>
                    </div>
                  </HStack>
                </div>
              )}

              {/* Upload Method Toggle */}
              {!editingId && (
                <div>
                  <label className="block text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-3">
                    Import Method
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setUploadMethod('file')}
                      className={`p-4 rounded-lg border-2 transition-all ${
                        uploadMethod === 'file'
                          ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                          : 'border-neutral-200 dark:border-neutral-700 hover:border-neutral-300 dark:hover:border-neutral-600'
                      }`}
                    >
                      <HStack spacing={3} align="start">
                        <Upload className={`w-5 h-5 ${
                          uploadMethod === 'file' 
                            ? 'text-brand-600 dark:text-brand-400' 
                            : 'text-neutral-400'
                        }`} />
                        <div className="text-left">
                          <div className={`font-medium ${
                            uploadMethod === 'file'
                              ? 'text-brand-900 dark:text-brand-100'
                              : 'text-neutral-900 dark:text-neutral-100'
                          }`}>
                            Upload File
                          </div>
                          <div className="text-xs text-neutral-600 dark:text-neutral-400 mt-0.5">
                            Browse and upload
                          </div>
                        </div>
                      </HStack>
                    </button>

                    <button
                      type="button"
                      onClick={() => setUploadMethod('path')}
                      className={`p-4 rounded-lg border-2 transition-all ${
                        uploadMethod === 'path'
                          ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                          : 'border-neutral-200 dark:border-neutral-700 hover:border-neutral-300 dark:hover:border-neutral-600'
                      }`}
                    >
                      <HStack spacing={3} align="start">
                        <FolderOpen className={`w-5 h-5 ${
                          uploadMethod === 'path' 
                            ? 'text-brand-600 dark:text-brand-400' 
                            : 'text-neutral-400'
                        }`} />
                        <div className="text-left">
                          <div className={`font-medium ${
                            uploadMethod === 'path'
                              ? 'text-brand-900 dark:text-brand-100'
                              : 'text-neutral-900 dark:text-neutral-100'
                          }`}>
                            File Path
                          </div>
                          <div className="text-xs text-neutral-600 dark:text-neutral-400 mt-0.5">
                            Specify location
                          </div>
                        </div>
                      </HStack>
                    </button>
                  </div>
                </div>
              )}

              {/* File Upload Area */}
              {!editingId && uploadMethod === 'file' && (
                <div>
                  <label className="block text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-2">
                    Dataset File <span className="text-danger-500">*</span>
                  </label>
                  <label
                    className={`flex flex-col items-center justify-center w-full h-40 border-2 border-dashed rounded-lg cursor-pointer transition-all ${
                      uploadedFile
                        ? 'border-success-400 bg-success-50 dark:bg-success-900/20'
                        : 'border-neutral-300 dark:border-neutral-700 hover:border-brand-400 dark:hover:border-brand-600 bg-neutral-50 dark:bg-neutral-800/50 hover:bg-brand-50 dark:hover:bg-brand-900/20'
                    }`}
                  >
                    <div className="flex flex-col items-center justify-center pt-5 pb-6 px-4">
                      {uploadedFile ? (
                        <>
                          <CheckCircle2 className="w-12 h-12 text-success-500 mb-3" />
                          <p className="text-sm font-medium text-success-700 dark:text-success-400 mb-1">
                            {uploadedFile.name}
                          </p>
                          <p className="text-xs text-success-600 dark:text-success-500">
                            {(uploadedFile.size / 1024 / 1024).toFixed(2)} MB • {uploadedFile.type}
                          </p>
                          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-2">
                            Click to change file
                          </p>
                        </>
                      ) : (
                        <>
                          <FileText className="w-12 h-12 text-neutral-400 mb-3" />
                          <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-1">
                            Click to upload or drag and drop
                          </p>
                          <p className="text-xs text-neutral-500 dark:text-neutral-400">
                            JSONL, CSV, TXT, or JSON files
                          </p>
                        </>
                      )}
                    </div>
                    <input
                      type="file"
                      accept=".json,.jsonl,.csv,.txt"
                      onChange={handleFileChange}
                      className="hidden"
                    />
                  </label>
                </div>
              )}

              {/* File Path Input */}
              {(editingId || uploadMethod === 'path') && (
                <div>
                  <label className="block text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-2">
                    File Path <span className="text-danger-500">*</span>
                  </label>
                  <Input
                    value={form.file_path}
                    onChange={(e) => setForm({ ...form, file_path: e.target.value })}
                    placeholder="/path/to/dataset.jsonl"
                    icon={<FolderOpen className="w-4 h-4" />}
                    required
                  />
                  <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                    Absolute or relative path to your dataset file
                  </p>
                </div>
              )}

              {/* Dataset Name */}
              <div>
                <label className="block text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-2">
                  Dataset Name <span className="text-danger-500">*</span>
                </label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g., Customer Support Dataset"
                  icon={<Database className="w-4 h-4" />}
                  required
                />
                <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                  A descriptive name for easy identification
                </p>
              </div>

              {/* Advanced Settings */}
              <div className="border-t border-neutral-200 dark:border-neutral-700 pt-4">
                <div className="flex items-center gap-2 mb-3">
                  <Info className="w-4 h-4 text-neutral-500" />
                  <h4 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                    Advanced Settings (Optional)
                  </h4>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                      Token Count
                    </label>
                    <Input
                      type="number"
                      value={form.token_count}
                      onChange={(e) => setForm({ ...form, token_count: Number(e.target.value) })}
                      placeholder="Auto-calculated"
                      min="0"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-neutral-700 dark:text-neutral-300 mb-2">
                      Quality Score (0-100)
                    </label>
                    <Input
                      type="number"
                      min="0"
                      max="100"
                      value={form.quality_score}
                      onChange={(e) => setForm({ ...form, quality_score: Number(e.target.value) })}
                      placeholder="85"
                    />
                  </div>
                </div>
              </div>

              {/* Format Guide */}
              {!editingId && (
                <div className="bg-neutral-50 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-neutral-600 dark:text-neutral-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <h5 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-2">
                        Supported Formats
                      </h5>
                      <div className="space-y-2 text-xs text-neutral-700 dark:text-neutral-300">
                        <div className="flex gap-2 items-start">
                          <Badge variant="neutral" size="sm">JSONL</Badge>
                          <code className="flex-1 bg-neutral-100 dark:bg-neutral-900 px-2 py-1 rounded">
                            {"{"}"instruction": "...", "output": "..."{"}"}
                          </code>
                        </div>
                        <div className="flex gap-2 items-start">
                          <Badge variant="neutral" size="sm">JSON</Badge>
                          <code className="flex-1 bg-neutral-100 dark:bg-neutral-900 px-2 py-1 rounded">
                            [{"{"}"instruction": "...", "output": "..."{"}"}, ...]
                          </code>
                        </div>
                        <div className="flex gap-2 items-start">
                          <Badge variant="neutral" size="sm">CSV</Badge>
                          <span className="flex-1 text-neutral-600 dark:text-neutral-400">
                            Headers: instruction,output
                          </span>
                        </div>
                        <div className="flex gap-2 items-start">
                          <Badge variant="neutral" size="sm">TXT</Badge>
                          <span className="flex-1 text-neutral-600 dark:text-neutral-400">
                            Plain text (one sample per line)
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </VStack>
          </ModalBody>
          <ModalFooter>
            <div className="flex justify-between items-center w-full">
              <p className="text-xs text-neutral-500 dark:text-neutral-400">
                {!editingId && uploadMethod === 'file' && uploadedFile && form.name ? (
                  <span className="text-success-600 dark:text-success-400 font-medium">
                    ✓ Ready to import
                  </span>
                ) : !editingId && uploadMethod === 'path' && form.file_path && form.name ? (
                  <span className="text-success-600 dark:text-success-400 font-medium">
                    ✓ Ready to import
                  </span>
                ) : editingId && form.name ? (
                  <span className="text-success-600 dark:text-success-400 font-medium">
                    ✓ Ready to update
                  </span>
                ) : (
                  <span>Please fill in required fields</span>
                )}
              </p>
              <HStack spacing={3}>
                <Button 
                  variant="ghost" 
                  onClick={() => {
                    setModalOpen(false);
                    setUploadedFile(null);
                  }} 
                  type="button"
                >
                  Cancel
                </Button>
                <Button 
                  variant="primary" 
                  type="submit"
                  disabled={uploading || (!editingId && uploadMethod === 'file' && !uploadedFile) || (!form.name)}
                >
                  {uploading ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Importing...
                    </>
                  ) : (
                    <>
                      {editingId ? <Edit2 className="w-4 h-4 mr-2" /> : <Upload className="w-4 h-4 mr-2" />}
                      {editingId ? 'Update Dataset' : 'Import Dataset'}
                    </>
                  )}
                </Button>
              </HStack>
            </div>
          </ModalFooter>
        </form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={deleteConfirmId !== null}
        onClose={() => setDeleteConfirmId(null)}
        size="sm"
      >
        <ModalHeader>
          <h3 className="text-xl font-semibold text-neutral-900 dark:text-neutral-100">
            Delete Dataset
          </h3>
        </ModalHeader>
        <ModalBody>
          <div className="flex items-start gap-3">
            <div className="p-2 bg-danger-50 dark:bg-danger-900/20 rounded-lg">
              <AlertCircle className="w-6 h-6 text-danger-600 dark:text-danger-400" />
            </div>
            <div>
              <p className="text-neutral-900 dark:text-neutral-100 font-medium mb-1">
                Are you sure?
              </p>
              <p className="text-sm text-neutral-600 dark:text-neutral-400">
                This action cannot be undone. The dataset will be permanently deleted.
              </p>
            </div>
          </div>
        </ModalBody>
        <ModalFooter>
          <HStack justify="end" spacing={3}>
            <Button variant="ghost" onClick={() => setDeleteConfirmId(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={() => deleteConfirmId && handleDelete(deleteConfirmId)}
            >
              Delete
            </Button>
          </HStack>
        </ModalFooter>
      </Modal>
    </Container>
  );
};

export default DatasetManager;
