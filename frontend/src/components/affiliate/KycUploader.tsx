import { useRef, useState } from 'react';
import { uploadDocument } from '@/api/affiliate/profile';
import { Button } from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';

interface KycUploaderProps {
  onUpload?: () => void;
}

export function KycUploader({ onUpload }: KycUploaderProps) {
  const [type, setType] = useState('W-9');
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();

  const handleFile = async (file: File) => {
    setLoading(true);
    try {
      await uploadDocument(file, type);
      toast.add({ title: 'Document uploaded', description: `${file.name} uploaded for review`, variant: 'success' });
      onUpload?.();
    } catch {
      toast.add({ title: 'Upload failed', description: 'Could not upload document', variant: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-slate-700">Document type</label>
      <select
        value={type}
        onChange={(e) => setType(e.target.value)}
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
      >
        <option value="W-9">W-9</option>
        <option value="W-8BEN">W-8BEN</option>
        <option value="W-8BEN-E">W-8BEN-E</option>
        <option value="identity">Proof of identity</option>
      </select>
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
      />
      <Button onClick={() => inputRef.current?.click()} isLoading={loading}>
        Upload document
      </Button>
    </div>
  );
}
