import React from 'react';
import { Button } from './button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './card';
import { AlertTriangle, X } from 'lucide-react';

interface ConfirmDeleteDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  assetName?: string;
  description?: string;
  isLoading?: boolean;
}

export function ConfirmDeleteDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  assetName,
  description,
  isLoading = false
}: ConfirmDeleteDialogProps) {
  if (!isOpen) return null;

  const displayText = description || (assetName ? `Are you sure you want to delete "${assetName}"?` : 'Are you sure you want to delete this item?');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm" 
        onClick={onClose}
      />
      
      {/* Modal */}
      <Card className="relative z-10 w-full max-w-md mx-4 shadow-2xl bg-gray-900 border-gray-700">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-red-900/30 rounded-full border border-red-800/50">
                <AlertTriangle className="h-5 w-5 text-red-400" />
              </div>
              <CardTitle className="text-lg font-semibold text-gray-100">
                {title}
              </CardTitle>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0 hover:bg-gray-800 text-gray-400 hover:text-gray-200"
              onClick={onClose}
              disabled={isLoading}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <p className="text-sm text-gray-300">
              {displayText}
            </p>
            
            <CardDescription className="text-xs text-gray-400">
              This will permanently delete:
            </CardDescription>
            
            <ul className="text-xs text-gray-400 space-y-1 ml-4">
              <li>• The asset and all its data</li>
              <li>• All associated apex domains</li>
              <li>• All discovered subdomains</li>
            </ul>
            
            <div className="mt-3 p-3 bg-blue-900/20 border border-blue-800/30 rounded-md">
              <p className="text-xs font-medium text-blue-300">
                ℹ️ Scan history will be preserved for future reference
              </p>
            </div>
            
            <div className="mt-3 p-3 bg-amber-900/20 border border-amber-800/30 rounded-md">
              <p className="text-xs font-medium text-amber-300">
                ⚠️ This action cannot be undone
              </p>
            </div>
          </div>
          
          <div className="flex space-x-3 pt-2">
            <Button
              variant="outline"
              className="flex-1 border-gray-600 text-gray-300 hover:bg-gray-800 hover:text-gray-100"
              onClick={onClose}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              className="flex-1 bg-red-600 hover:bg-red-700 text-white"
              onClick={onConfirm}
              disabled={isLoading}
            >
              {isLoading ? (
                <div className="flex items-center space-x-2">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  <span>Deleting...</span>
                </div>
              ) : (
                'Delete Asset'
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
