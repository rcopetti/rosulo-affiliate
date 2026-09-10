import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Key, Copy, Check, Globe, Shield } from 'lucide-react';
import { rotateApiKey, getIntegrationTenant, updateAllowedDomains } from '@/api/admin/integrations';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { useToast } from '@/components/ui/Toast';

export function IntegrationPage() {
  const toast = useToast();
  const [apiKey, setApiKey] = useState<string | null>(localStorage.getItem('rosulo:adminApiKey'));
  const [copied, setCopied] = useState(false);
  const [domainInput, setDomainInput] = useState('');

  const { data: tenant, isLoading } = useQuery({
    queryKey: ['admin-integration'],
    queryFn: getIntegrationTenant,
  });

  const [domains, setDomains] = useState<string[]>([]);
  useEffect(() => {
    if (tenant?.allowed_domains) {
      setDomains(tenant.allowed_domains);
    }
  }, [tenant?.allowed_domains]);

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

  const updateDomains = useMutation({
    mutationFn: updateAllowedDomains,
    onSuccess: () => toast.add({ title: 'Domains updated', variant: 'success' }),
    onError: () => toast.add({ title: 'Update failed', description: 'Could not save allowed domains', variant: 'error' }),
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

  const addDomain = () => {
    const value = domainInput.trim().toLowerCase();
    if (!value) return;
    if (domains.includes(value)) {
      setDomainInput('');
      return;
    }
    setDomains([...domains, value]);
    setDomainInput('');
  };

  const removeDomain = (d: string) => setDomains(domains.filter((x) => x !== d));

  const trackingSnippet = `<script>
  (function() {
    const params = new URLSearchParams(location.search);
    const code = params.get('rc') || 'YOUR_TRACKING_CODE';
    const page = location.href;
    const ref = document.referrer || '';
    fetch('${apiBase}/tracking/track-click', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tracking_code: code,
        customer_id: null,
        referer: ref,
        page_url: page,
      }),
    });
  })();
</script>`;

  if (isLoading) return <div className="p-4 text-slate-600">Loading integration settings…</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Integration</h1>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5" />
            Allowed domains
          </CardTitle>
        </CardHeader>
        <div className="space-y-4 px-6 pb-6">
          <p className="text-sm text-slate-600">
            Only requests from these domains can call the public click-tracking endpoint. Use <code>*.allbum.me</code> to allow all subdomains.
          </p>
          <div className="flex items-center gap-2">
            <Input
              value={domainInput}
              onChange={(e) => setDomainInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addDomain()}
              placeholder="e.g. allbum.me or *.allbum.me"
            />
            <Button onClick={addDomain} variant="secondary">Add</Button>
          </div>
          <div className="space-y-2">
            {domains.length ? (
              <ul className="space-y-1">
                {domains.map((d) => (
                  <li key={d} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm">
                    <span className="font-mono text-slate-700">{d}</span>
                    <button onClick={() => removeDomain(d)} className="text-slate-400 hover:text-red-500">Remove</button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">No allowed domains configured yet.</p>
            )}
          </div>
          <Button onClick={() => updateDomains.mutate({ allowed_domains: domains })} isLoading={updateDomains.isPending}>
            Save allowed domains
          </Button>
        </div>
      </Card>

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
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Direct tracking snippet
          </CardTitle>
        </CardHeader>
        <div className="space-y-4 px-6 pb-6">
          <p className="text-sm text-slate-600">
            Paste this in the <code>&lt;head&gt;</code> of your landing pages. It records a click using the public <code>tracking_code</code> from the URL. The API key is not exposed in the browser.
          </p>
          <pre className="overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-50">
            <code>{trackingSnippet}</code>
          </pre>
          <p className="text-sm text-slate-600">
            Affiliate links should point to your domain with the campaign code, e.g.
            <code className="ml-1 rounded bg-slate-100 px-1 py-0.5">https://allbum.me/?rc=ABC123</code>.
          </p>
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Server-to-server event API</CardTitle>
        </CardHeader>
        <div className="space-y-4 px-6 pb-6">
          <div className="text-sm text-slate-600">
            <p><strong>Base URL:</strong> <code className="rounded bg-slate-100 px-1 py-0.5">{apiBase}</code></p>
            <p className="mt-1"><strong>Auth header:</strong> <code className="rounded bg-slate-100 px-1 py-0.5">X-API-Key: {apiKey || '&lt;your-api-key&gt;'}</code></p>
          </div>

          <h3 className="font-semibold text-slate-900">Tracking a sale</h3>
          <pre className="overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-50">
            <code>{`curl -X POST ${apiBase}/events \\
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
  }'`}</code>
          </pre>

          <h3 className="font-semibold text-slate-900">Supported event types</h3>
          <ul className="list-disc pl-5 text-sm text-slate-600">
            <li><code>click</code> — public tracking endpoint, requires allowed domain.</li>
            <li><code>lead</code> — server-to-server with API key.</li>
            <li><code>sale</code> — server-to-server with API key, include <code>amount</code>, <code>currency</code>, and <code>payment_sequence</code>.</li>
          </ul>
        </div>
      </Card>
    </div>
  );
}
