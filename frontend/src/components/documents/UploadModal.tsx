import { X, Upload } from 'lucide-react';
import { DOC_CATEGORIES, DOC_DEPARTMENTS, DOC_TYPES } from '@/data/documentsData';

interface UploadModalProps {
  open: boolean;
  onClose: () => void;
}

export default function UploadModal({ open, onClose }: UploadModalProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4"
      data-testid="upload-modal"
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between p-5 border-b border-[#e2eedd]">
          <h2 className="text-base font-semibold text-[#1a2e14]">Upload Document</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-[#f0f7ed]"
            data-testid="button-close-modal"
          >
            <X size={16} className="text-[#5a7a52]" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {/* Drop zone */}
          <div className="border-2 border-dashed border-[#ddecd6] rounded-xl p-8 text-center bg-[#f8fdf6]">
            <Upload size={24} className="text-[#9ab88e] mx-auto mb-2" />
            <p className="text-sm text-[#5a7a52] font-medium">Drop files here or click to browse</p>
            <p className="text-xs text-[#9ab88e] mt-1">PDF, DOC, DOCX, XLS up to 50MB</p>
          </div>

          {/* Document Name */}
          <div>
            <label className="block text-xs font-medium text-[#1a2e14] mb-1.5">Document Name</label>
            <input
              className="w-full border border-[#ddecd6] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#4a7c3f]/30 focus:border-[#4a7c3f]"
              placeholder="Enter document name"
              data-testid="input-doc-name"
            />
          </div>

          {/* Category */}
          <div>
            <label className="block text-xs font-medium text-[#1a2e14] mb-1.5">Category</label>
            <select
              className="w-full border border-[#ddecd6] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#4a7c3f]/30"
              data-testid="select-category"
            >
              <option value="">Select Category</option>
              {DOC_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          {/* Department */}
          <div>
            <label className="block text-xs font-medium text-[#1a2e14] mb-1.5">Department</label>
            <select
              className="w-full border border-[#ddecd6] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#4a7c3f]/30"
              data-testid="select-department"
            >
              <option value="">Select Department</option>
              {DOC_DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>

          {/* Type */}
          <div>
            <label className="block text-xs font-medium text-[#1a2e14] mb-1.5">Type</label>
            <select
              className="w-full border border-[#ddecd6] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#4a7c3f]/30"
              data-testid="select-type"
            >
              <option value="">Select Type</option>
              {DOC_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>

        <div className="flex gap-3 p-5 border-t border-[#e2eedd]">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2.5 border border-[#ddecd6] text-sm font-medium text-[#5a7a52] rounded-lg hover:bg-[#f0f7ed] transition-colors"
            data-testid="button-cancel-upload"
          >
            Cancel
          </button>
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2.5 bg-[#4a7c3f] text-white text-sm font-medium rounded-lg hover:bg-[#3d6834] transition-colors"
            data-testid="button-confirm-upload"
          >
            Upload
          </button>
        </div>
      </div>
    </div>
  );
}
