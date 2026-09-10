import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Key, Copy, Check } from 'lucide-react';
import { rotateApiKey } from '@/api/admin/integrations';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { useToast } from '@/components/ui/Toast';

export function IntegrationPage() {
  const toast = useToast();
  const [apiKey, setApiKey] = useState<string | null>(localStorage.getItem('rosulo:adminApiKey'));
  const [copied, setCopied] = useState(false);
  const tenantId = localStorage.getItem('rosulo:adminTenantId') || '';

  const apiBase = import.meta.env.VITE_API_BASE_URL?.startsWith('http')
    ? import.meta.env.VITE_API_BASE_URL
    : `${window.location.origin}${import.meta.env.VITE_API_BASE_URL || '/api/v1'}`;

  const rotate = useMutation({
    mutationFn: rotateApiKey,
    onSuccess: (data) => {
      setApiKey(data.api_key);
      localStorage.setItem('rosulo:adminApiKey', data.api_key);
      toast.add({ title: 'API key generated', description: 'Copy it now — it will not be shown again.', variant: 'success' });
    },
    onError: () => toast.add({ title: 'Failed', description: 'Could not generate API key', variant: 'error' }),
  });

  const copyKey = async () => {
    if (!apiKey) return;
    try {
      await navigator.clipboard.writeText(apiKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.add({ title: 'Copy failed', description: 'Please copy the key manually', variant: 'error' });
    }
  };

  const clickExample = `curl -X POST ${apiBase}/events \\
  -H "X-API-Key: ${apiKey || '<your-api-key>'}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "event_id": "click-001",
    "type": "click",
    "campaign_id": "<campaign-id>",
    "customer_id": "cust-001",
    "referer": "https://example.com",
    "page_url": "https://yoursite.com/offer"
  }'`;

  const saleExample = `curl -X POST ${apiBase}/events \\
  -H "X-API-Key: ${apiKey || '<your-api-key>'}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "event_id": "sale-001",
    "type": "sale",
    "campaign_id": "<campaign-id>",
    "customer_id": "cust-001",
    "amount": 100.00,
    "currency": "USD",
    "payment_sequence": 1
  }'`;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Integration</h1>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Key className="h-5 w-5" />
            API Key
          </CardTitle>
        </CardHeader>
        <div className="space-y-4 px-6 pb-6">
          <p className="text-sm text-slate-600">
            Use this key to send server-to-server events to Rosulo Affiliate. Keep it secret.
          </p>

          {apiKey ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={apiKey}
                  className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm font-mono text-slate-700"
                />
                <Button onClick={copyKey} variant="secondary" size="sm">
                  {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                </Button>
              </div>
              <p className="text-xs text-amber-600">
                Copy this key now. It will not be displayed again after you leave this page unless you generate a new one.
              </p>
            </div>
          ) : (
            <p className="text-sm text-slate-500">No API key has been generated yet.</p>
          )}

          <Button onClick={() => rotate.mutate()} isLoading={rotate.isPending}>
            {apiKey ? 'Regenerate API key' : 'Generate API key'}
          </Button>
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Integration details</CardTitle>
        </CardHeader>
        <div className="space-y-4 px-6 pb-6">
          <div className="text-sm text-slate-600">
            <p><strong>Base URL:</strong> <code className="rounded bg-slate-100 px-1 py-0.5">{apiBase}</code></p>
            <p className="mt-1"><strong>Tenant ID:</strong> <code className="rounded bg-slate-100 px-1 py-0.5">{tenantId || 'N/A'}</code></p>
            <p className="mt-1"><strong>Auth header:</strong> <code className="rounded bg-slate-100 px-1 py-0.5">X-API-Key</code></p>
          </div>

          <h3 className="font-semibold text-slate-900">Tracking a click</h3>
          <pre className="overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-50">
            <code>{clickExample}</code>
          </pre>

          <h3 className="font-semibold text-slate-900">Tracking a sale</h3>
          <pre className="overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-50">
            <code>{saleExample}</code>
          </pre>

          <h3 className="font-semibold text-slate-900">Supported event types</h3>
          <ul className="list-disc pl-5 text-sm text-slate-600">
            <li><code>click</code> — includes <code>referer</code> and <code>page_url</code></li>
            <li><code>lead</code></li>
            <li><code>sale</code> — include <code>amount</code>, <code>currency</code>, and <code>payment_sequence</code></li>
          </ul>
        </div>
      </Card>
    </div>
  );
}
