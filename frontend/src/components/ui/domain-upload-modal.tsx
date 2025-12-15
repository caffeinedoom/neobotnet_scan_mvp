import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Upload, FileText, X } from 'lucide-react';
import { toast } from 'sonner';
import { assetAPI } from '@/lib/api/assets';

interface DomainUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  onComplete?: () => void;
  assetId?: string;
  assetName?: string;
  asset?: {
    id: string;
    name: string;
  };
}

interface UploadResult {
  summary: {
    added: number;
    duplicates: number;
    failed: number;
    total_lines_processed: number;
  };
}

export function DomainUploadModal({ 
  isOpen, 
  onClose, 
  onSuccess, 
  onComplete,
  assetId, 
  assetName,
  asset 
}: DomainUploadModalProps) {
  const [uploadingFile, setUploadingFile] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);

  // Support both prop patterns
  const finalAssetId = assetId || asset?.id;
  const finalAssetName = assetName || asset?.name;
  const finalOnSuccess = onSuccess || onComplete;

  if (!finalAssetId || !finalAssetName) {
    console.error('DomainUploadModal: Missing required asset information');
    return null;
  }

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      // Validate file type
      if (!file.name.match(/\.(txt|list|domains)$/i)) {
        toast.error('Please select a text file (.txt, .list, or .domains)');
        return;
      }

      // Validate file size (max 5MB)
      if (file.size > 5 * 1024 * 1024) {
        toast.error('File size must be less than 5MB');
        return;
      }

      setSelectedFile(file);
      setUploadResult(null);
    }
  };

  const handleFileUpload = async () => {
    if (!selectedFile) return;
    
    try {
      setUploadingFile(true);
      
      // Use proper asset API with cookie-based authentication
      const apiResponse = await assetAPI.bulkUploadDomains(finalAssetId, selectedFile);
      
      // Map API response to expected modal format
      const result = {
        summary: {
          added: apiResponse.added_domains,
          duplicates: apiResponse.duplicate_domains,
          failed: apiResponse.invalid_domains,
          total_lines_processed: apiResponse.total_lines
        }
      };
      
      setUploadResult(result);
      
      // Reset file selection
      setSelectedFile(null);
      
      // Show success notification with details
      toast.success(
        `Upload completed! Added ${result.summary.added} domains to ${finalAssetName}`, 
        {
          description: result.summary.duplicates > 0 
            ? `${result.summary.duplicates} duplicates skipped` 
            : undefined
        }
      );
      
              // Trigger success callback to refresh asset list
        finalOnSuccess?.();
      
      // Close modal after successful upload
      setTimeout(() => {
        onClose();
      }, 1500);
      
    } catch (error) {
      console.error('Failed to upload file:', error);
      
      // Handle API errors properly
      let errorMessage = 'Unknown error occurred';
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (typeof error === 'object' && error !== null && 'response' in error) {
        // Handle axios error responses
        const axiosError = error as { response?: { data?: { detail?: string } }; message?: string };
        errorMessage = axiosError.response?.data?.detail || axiosError.message || 'Upload failed';
      }
      
      toast.error(`Failed to upload file: ${errorMessage}`);
    } finally {
      setUploadingFile(false);
    }
  };

  const handleClose = () => {
    setSelectedFile(null);
    setUploadResult(null);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-900 rounded-lg p-6 w-full max-w-md mx-4">
        {/* Modal Header */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Upload Domains</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClose}
            className="h-8 w-8 p-0"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Asset Info */}
        <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
          <p className="text-sm text-muted-foreground">Adding domains to:</p>
          <p className="font-medium">{finalAssetName}</p>
        </div>

        {/* Upload Interface */}
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium">Upload Domain List</label>
            <p className="text-xs text-muted-foreground mb-3">
              Upload a text file with one domain per line. Supports .txt, .list, and .domains files.
            </p>

            {/* File Input */}
            <div className="space-y-3">
              <input
                type="file"
                accept=".txt,.list,.domains"
                onChange={handleFileSelect}
                className="hidden"
                id="domain-file-input"
              />
              <label
                htmlFor="domain-file-input"
                className="flex flex-col items-center justify-center border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-6 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
              >
                {selectedFile ? (
                  <div className="text-center">
                    <FileText className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                    <p className="font-medium">{selectedFile.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {(selectedFile.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                ) : (
                  <div className="text-center">
                    <Upload className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                    <p className="font-medium">Click to upload file</p>
                    <p className="text-xs text-muted-foreground">
                      .txt, .list, or .domains files
                    </p>
                  </div>
                )}
              </label>
            </div>

            {/* Upload Button */}
            {selectedFile && (
              <div className="flex justify-between items-center pt-3">
                <Button
                  onClick={handleFileUpload}
                  disabled={uploadingFile}
                  className="flex-1 mr-2"
                >
                  {uploadingFile ? (
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent mr-2" />
                  ) : (
                    <Upload className="h-4 w-4 mr-2" />
                  )}
                  {uploadingFile ? 'Uploading...' : 'Upload'}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setSelectedFile(null)}
                  disabled={uploadingFile}
                >
                  Clear
                </Button>
              </div>
            )}
          </div>
        </div>

        {/* Upload Result Summary */}
        {uploadResult && (
          <div className="mt-4 p-4 bg-background border rounded-lg">
            <h4 className="font-medium mb-2">Upload Results</h4>
            <div className="grid grid-cols-4 gap-4 text-sm text-center">
              <div>
                <div className="text-lg font-semibold text-white">{uploadResult.summary.added}</div>
                <div className="text-muted-foreground">Added</div>
              </div>
              <div>
                <div className="text-lg font-semibold text-white">{uploadResult.summary.duplicates}</div>
                <div className="text-muted-foreground">Duplicates</div>
              </div>
              <div>
                <div className="text-lg font-semibold text-white">{uploadResult.summary.failed}</div>
                <div className="text-muted-foreground">Failed</div>
              </div>
              <div>
                <div className="text-lg font-semibold text-white">{uploadResult.summary.total_lines_processed}</div>
                <div className="text-muted-foreground">Total Lines</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
