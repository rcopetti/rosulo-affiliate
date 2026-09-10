import { useState } from 'react';
import { Term } from '@/api/types';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';

interface TermEditorProps {
  term: Term;
  onSave: (term: Term) => void;
  onDelete?: (id: string) => void;
}

export function TermEditor({ term, onSave, onDelete }: TermEditorProps) {
  const [seq, setSeq] = useState(term.payment_sequence);
  const [pct, setPct] = useState(term.commission_percent);

  return (
    <div className="grid gap-2 rounded-lg border border-slate-200 p-4 sm:grid-cols-4">
      <Input label="Sequence" value={seq} onChange={(e) => setSeq(e.target.value)} />
      <Input label="Commission %" type="number" value={pct} onChange={(e) => setPct(Number(e.target.value))} />
      <div className="flex items-end gap-2">
        <Button size="sm" onClick={() => onSave({ ...term, payment_sequence: seq, commission_percent: pct })}>
          Save
        </Button>
        {onDelete && (
          <Button variant="danger" size="sm" onClick={() => onDelete(term.id)}>
            Delete
          </Button>
        )}
      </div>
    </div>
  );
}
