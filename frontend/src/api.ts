// ── API client — all calls go through here ───────────────────────────────────
// In dev: Vite proxy forwards /api → http://localhost:8000
// In prod: VITE_API_URL env var (e.g. https://cpa-backend.onrender.com)

const BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  timestamp: string;
}

export interface StatusResponse {
  groq_configured: boolean;
  apify_configured: boolean;
  mock_mode: boolean;
  database_url: string;
  input_pdfs: number;
  reports_generated: number;
  invoices_in_db: number;
  feedback_corrections: number;
  pipeline_status: string;
}

export interface DashboardResponse {
  run_summary: { invoices_processed: number; total_invoice_value_usd: number };
  severity_breakdown: { critical: number; high: number; medium: number; low: number };
  top_vendors_by_spend: Record<string, number>;
  top_anomaly_types: Record<string, number>;
  most_overpriced_routes: Record<string, { standard: number; charged: number; delta_pct: number }>;
  per_invoice_summary: Array<{
    invoice_number: string;
    vendor_name: string;
    invoice_date: string | null;
    total_amount: number;
    currency: string;
    severity: string;
    anomaly_count: number;
    report_path?: string;
  }>;
  _empty?: boolean;
}

export interface Invoice {
  id: number;
  vendor_name: string | null;
  invoice_number: string | null;
  invoice_date: string | null;
  currency: string | null;
  incoterms: string | null;
  total_amount: number | null;
  status: string | null;
  created_at: string | null;
}

export interface InvoicesResponse {
  invoices: Invoice[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

export interface ReportFile {
  filename: string;
  size_bytes: number;
  modified_at: string;
}

export interface ReportsResponse {
  reports: ReportFile[];
  count: number;
}

export interface PipelineState {
  status: 'idle' | 'running' | 'completed' | 'failed';
  started_at: string | null;
  completed_at: string | null;
  last_result: Record<string, unknown> | null;
  error: string | null;
}

export interface FeedbackEntry {
  id: number;
  invoice_id: number;
  field_name: string;
  original_value: string;
  corrected_value: string;
  notes: string | null;
  created_at: string;
}

// ── Endpoints ──────────────────────────────────────────────────────────────────

export const api = {
  health: () => request<HealthResponse>('/api/health'),

  status: () => request<StatusResponse>('/api/status'),

  dashboard: () => request<DashboardResponse>('/api/dashboard'),

  invoices: (page = 1, pageSize = 20) =>
    request<InvoicesResponse>(`/api/invoices?page=${page}&page_size=${pageSize}`),

  invoice: (id: number) => request<Invoice & { audit_report: unknown }>(`/api/invoices/${id}`),

  reports: () => request<ReportsResponse>('/api/reports'),

  report: (filename: string) => request<unknown>(`/api/reports/${filename}`),

  pipelineRun: (exportCsv = false) =>
    request<{ message: string; status: string }>('/api/pipeline/run', {
      method: 'POST',
      body: JSON.stringify({ export_csv: exportCsv }),
    }),

  pipelineStatus: () => request<PipelineState>('/api/pipeline/status'),

  pipelineStream: (): EventSource => new EventSource(`${BASE}/api/pipeline/stream`),

  upload: (files: FileList | File[]) => {
    const form = new FormData();
    Array.from(files).forEach((f) => form.append('files', f));
    return fetch(`${BASE}/api/upload`, { method: 'POST', body: form }).then((r) => {
      if (!r.ok) throw new Error(`Upload failed: ${r.status}`);
      return r.json() as Promise<{ uploaded: string[]; count: number }>;
    });
  },

  submitFeedback: (invoiceId: number, data: {
    field_name: string;
    original_value: string;
    corrected_value: string;
    notes?: string;
  }) =>
    request(`/api/invoices/${invoiceId}/feedback`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  feedback: () => request<{ entries: FeedbackEntry[]; total: number; most_common_corrections: Record<string, number> }>('/api/feedback'),

  clearCache: () =>
    request<{ message: string; removed: number }>('/api/cache', { method: 'DELETE' }),
};
