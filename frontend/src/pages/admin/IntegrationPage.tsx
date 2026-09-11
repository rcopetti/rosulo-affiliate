import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Key, Copy, Check, Globe, Shield } from 'lucide-react';
import { rotateApiKey, getIntegrationTenant, updateAllowedDomains } from '@/api/admin/integrations';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Tabs } from '@/components/ui/Tabs';
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

  const tenantId = localStorage.getItem('rosulo:adminTenantId') || '';

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
    const code = params.get('rc');
    if (!code) return;
    const page = location.href;
    const ref = document.referrer || '';
    fetch(window.location.origin + '/rosulo/track-click', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tracking_code: code,
        customer_id: null,
        referer: ref,
        page_url: page,
      }),
    })
    .then(r => r.json())
    .then(data => {
      if (data.click_id) {
        const apex = window.location.hostname.replace(/^www\./, '');
        const cookieDomain = '.' + apex;
        document.cookie = 'rosulo_click_id=' + data.click_id +
          '; path=/; Secure; SameSite=Lax; Max-Age=2592000; domain=' + cookieDomain;
      }
    });
  })();
</script>`;

  const clickAiPrompt = `I need to add the Rosulo Affiliate click-tracking snippet to a website.

Context:
- This website domain: ${domains.join(', ') || '[add allowed domains above]'}
- Rosulo Affiliate API base: ${apiBase}
- Public click endpoint on the website backend: POST <your-backend-domain>/rosulo/track-click
- Rosulo public click endpoint (called by the backend, not the browser): POST ${apiBase}/tracking/track-click
- Affiliate landing links have this format: https://<domain>/?rc=<TRACKING_CODE>

Please provide:
1. A JavaScript snippet to include in the <head> of every landing page that:
   - Returns immediately if the URL does not contain a ?rc query parameter.
   - If ?rc is present, sends { tracking_code, referer, page_url } to the website's own backend endpoint (e.g. /rosulo/track-click).
   - The website backend should then forward the request to ${apiBase}/tracking/track-click, passing the original Origin/Referer headers from the browser so the Rosulo allowlist check passes.
   - The backend returns the Rosulo response to the browser.
   - Sets a first-party cookie named "rosulo_click_id" with the returned click_id using:
       path=/; Secure; SameSite=Lax; Max-Age=2592000 (30 days); domain=.<your-apex-domain>
   - For the domain, compute the apex from the current hostname or hardcode it to the site apex (e.g. .allbum.me).
2. A short note that the browser never calls the Rosulo API directly and that the API key must not be exposed in the browser.
3. A note that the registration handler will read the "rosulo_click_id" cookie and send a lead event to Rosulo, and that the lead event response contains an "id" field that should be stored as lead_id with the user account. Later sale events use that stored lead_id.`;

  const saleCurl = `curl -X POST ${apiBase}/events \\
  -H "X-API-Key: ${apiKey || '<your-api-key>'}" \\
  -H "X-Tenant-Id: ${tenantId}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "event_id": "sale-001",
    "type": "sale",
    "lead_id": "<lead_id-stored-with-user>",
    "customer_id": "cust-001",
    "amount": 100.00,
    "currency": "USD",
    "payment_sequence": 1
  }'`;

  const saleAiPrompt = `I need a complete Rosulo Affiliate integration for my website. Please implement the full flow in the language of my project.

## Context
- Rosulo Affiliate API base URL: ${apiBase}
- Tenant ID: ${tenantId}
- Server-to-server API key: ${apiKey || '<your-api-key>'}
- Auth header: X-API-Key: ${apiKey || '<your-api-key>'}
- Optional tenant header: X-Tenant-Id: ${tenantId}
- Rosulo events endpoint (called from your backend): POST ${apiBase}/events
- Rosulo public click endpoint (called from your backend): POST ${apiBase}/tracking/track-click
- Tenant public click endpoint (called from the browser): POST <your-backend-domain>/rosulo/track-click
- Allowed domains: ${domains.join(', ') || '[add allowed domains above]'}

## 1. Frontend click tracking
Add a JavaScript snippet in the <head> of every landing page:
- Read the ?rc=<TRACKING_CODE> query parameter.
- If ?rc is missing, do nothing.
- If ?rc is present, POST to your own backend endpoint (e.g. /rosulo/track-click or https://<your-backend-domain>/rosulo/track-click) with JSON body { tracking_code, referer, page_url }.
- Your backend should forward the request to ${apiBase}/tracking/track-click, preserving the browser's Origin/Referer headers so the Rosulo allowlist check passes.
- Your backend returns the Rosulo response { click_id, campaign_id } to the browser.
- Set a first-party cookie named "rosulo_click_id" with the returned click_id, using:
    path=/; Secure; SameSite=Lax; Max-Age=2592000 (30 days); domain=.<your-apex-domain>
- Do not expose the Rosulo API key in the browser and do not call the Rosulo API directly from the browser.

## 2. Lead tracking (registration)
When a user registers or signs up:
- Read the "rosulo_click_id" cookie from the request.
- If the cookie is missing, do not send a lead event.
- If present, POST to ${apiBase}/events with:
    - event_id: a unique idempotent id for this lead
    - type: "lead"
    - click_id: the value from the "rosulo_click_id" cookie
    - customer_id: the user's internal id
    - customer_email: the user's email masked for privacy. Masking rules:
        - Split at "@" into local and domain parts.
        - If the local part is 4 or fewer characters, replace the entire local part with "****".
        - Otherwise keep the first 2 and last 1 character of the local part and replace the middle with "***".
        - Example: john.doe@example.com -> jo***e@example.com; ab@example.com -> ****@example.com.
- The backend will resolve the click_id to the correct campaign and affiliate.
- The response contains an "id" field. Store that value as the lead_id with the user account (database column or metadata). Sale events will use this lead_id.

## 3. Sale tracking (payment)
When a payment is confirmed:
- Use the lead_id that was stored with the user account during registration.
- POST to ${apiBase}/events with:
    - event_id: a unique idempotent id for this sale
    - type: "sale"
    - lead_id: the stored lead_id
    - customer_id: the user's internal id (optional, will be inherited from the lead if omitted)
    - amount: the payment amount (number)
    - currency: 3-letter code such as "USD"
    - payment_sequence: integer 1 for the first payment, 2 for the second, 3 for the third, etc.
- The backend will resolve the lead_id to the correct campaign and affiliate.
- Call the endpoint only after the payment is confirmed and successful.

## Constraints
- The API key must be stored in an environment variable, never in the frontend or source code.
- Mask customer_email before sending it.
- Use the same event_id for retries to keep idempotency.
- Add a small exponential backoff for HTTP 5xx responses.
- Never call the server-to-server /events endpoint directly from the browser.

Please output a complete, copy-paste-ready implementation: the frontend snippet, the backend lead handler, and the backend sale handler.`;

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
        <div className="px-6 pb-6">
          <Tabs
            defaultTab="manual"
            tabs={[
              {
                id: 'manual',
                label: 'Manual',
                content: (
                  <div className="space-y-4">
                    <p className="text-sm text-slate-600">
                      Paste this in the <code>&lt;head&gt;</code> of your landing pages. It runs only when the URL has a <code>?rc=</code> query parameter and sends the tracking data to your own backend endpoint <code>/rosulo/track-click</code>. Your backend should forward it to <code>${apiBase}/tracking/track-click</code> and return the <code>click_id</code>. The snippet stores the <code>click_id</code> in a first-party cookie named <code>rosulo_click_id</code> so lead and sale handlers can attribute conversions. The Rosulo API key is not exposed in the browser.
                    </p>
                    <pre className="overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-50">
                      <code>{trackingSnippet}</code>
                    </pre>
                    <p className="text-sm text-slate-600">
                      Affiliate links should point to your domain with the campaign code, e.g.
                      <code className="ml-1 rounded bg-slate-100 px-1 py-0.5">https://allbum.me/?rc=ABC123</code>.
                    </p>
                  </div>
                ),
              },
              {
                id: 'ai',
                label: 'AI Prompt',
                content: (
                  <div className="space-y-4">
                    <p className="text-sm text-slate-600">
                      Paste this prompt into an AI assistant to generate a customized tracking snippet for your project.
                    </p>
                    <pre className="overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-50">
                      <code>{clickAiPrompt}</code>
                    </pre>
                  </div>
                ),
              },
            ]}
          />
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Server-to-server event API</CardTitle>
        </CardHeader>
        <div className="px-6 pb-6">
          <Tabs
            defaultTab="manual"
            tabs={[
              {
                id: 'manual',
                label: 'Manual',
                content: (
                  <div className="space-y-5">
                    <div className="text-sm text-slate-600">
                      <p><strong>Base URL:</strong> <code className="rounded bg-slate-100 px-1 py-0.5">{apiBase}</code></p>
                      <p className="mt-1"><strong>Auth header:</strong> <code className="rounded bg-slate-100 px-1 py-0.5">X-API-Key: {apiKey || '&lt;your-api-key&gt;'}</code></p>
                      <p className="mt-1"><strong>Tenant header:</strong> <code className="rounded bg-slate-100 px-1 py-0.5">X-Tenant-Id: {tenantId || 'N/A'}</code></p>
                    </div>

                    <div className="space-y-2">
                      <h3 className="font-semibold text-slate-900">Lead tracking</h3>
                      <p className="text-sm text-slate-600">
                        When a user registers, read the <code>rosulo_click_id</code> cookie. If it exists, send a <code>lead</code> event. Store the returned <code>id</code> from the API response as <code>lead_id</code> with the user account; it will be used for sale attribution.
                      </p>
                      <pre className="overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-50">
                        <code>{`curl -X POST ${apiBase}/events \\
  -H "X-API-Key: ${apiKey || '<your-api-key>'}" \\
  -H "X-Tenant-Id: ${tenantId}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "event_id": "lead-001",
    "type": "lead",
    "click_id": "<rosulo_click_id-from-cookie>",
    "customer_id": "user-123",
    "customer_email": "jo***e@example.com"
  }'`}</code>
                      </pre>
                      <p className="text-sm text-slate-600">
                        Mask the email before sending: <code>john.doe@example.com</code> becomes <code>jo***e@example.com</code>.
                      </p>
                    </div>

                    <div className="space-y-2">
                      <h3 className="font-semibold text-slate-900">Sale tracking</h3>
                      <p className="text-sm text-slate-600">
                        When a payment is confirmed, send a <code>sale</code> event using the stored <code>lead_id</code>. Use <code>payment_sequence</code> 1 for the first payment, 2 for the second, and so on.
                      </p>
                      <pre className="overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-50">
                        <code>{saleCurl}</code>
                      </pre>
                    </div>

                    <h3 className="font-semibold text-slate-900">Supported event types</h3>
                    <ul className="list-disc pl-5 text-sm text-slate-600">
                      <li><code>click</code> — public tracking endpoint, requires allowed domain.</li>
                      <li><code>lead</code> — server-to-server with API key, send after registration.</li>
                      <li><code>sale</code> — server-to-server with API key, send only after confirmed payment.</li>
                    </ul>
                  </div>
                ),
              },
              {
                id: 'ai',
                label: 'AI Prompt',
                content: (
                  <div className="space-y-4">
                    <p className="text-sm text-slate-600">
                      Paste this prompt into an AI assistant to generate a backend integration for sending sale events.
                    </p>
                    <pre className="overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-50">
                      <code>{saleAiPrompt}</code>
                    </pre>
                  </div>
                ),
              },
            ]}
          />
        </div>
      </Card>
    </div>
  );
}
