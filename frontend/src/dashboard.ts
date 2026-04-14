import { api, type DashboardResponse, type Invoice, type PipelineState, type FeedbackEntry, type StatusResponse } from './api';

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n: number | null | undefined): string {
  if (n == null) return '—';
  return n.toLocaleString('en-US');
}

function fmtUsd(n: number | null | undefined): string {
  if (n == null) return '—';
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(1)}K`;
  return `$${n.toFixed(2)}`;
}

function setText(id: string, text: string): void {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function severityBadge(sev: string): string {
  const s = (sev ?? '').toLowerCase();
  if (s === 'critical') return `<span class="px-3 py-1 bg-error-container text-on-error-container rounded-full text-[10px] font-bold uppercase">Critical</span>`;
  if (s === 'high') return `<span class="px-3 py-1 bg-primary/20 text-primary border border-primary/30 rounded-full text-[10px] font-bold uppercase">High</span>`;
  if (s === 'medium') return `<span class="px-3 py-1 bg-yellow-500/20 text-yellow-300 border border-yellow-500/30 rounded-full text-[10px] font-bold uppercase">Medium</span>`;
  if (s === 'extracted') return `<span class="px-3 py-1 bg-primary/10 text-primary rounded-full text-[10px] font-bold uppercase">Extracted</span>`;
  return `<span class="px-3 py-1 bg-tertiary-fixed/20 text-tertiary-fixed rounded-full text-[10px] font-bold uppercase">${s || 'Low'}</span>`;
}

function appendLog(msg: string, cls = 'text-slate-400'): void {
  const container = document.getElementById('pipeline-log');
  if (!container) return;
  const now = new Date().toLocaleTimeString('en-US', { hour12: false });
  const p = document.createElement('p');
  p.className = `${cls} mb-1`;
  p.textContent = `[${now}] ${msg}`;
  container.appendChild(p);
  container.scrollTop = container.scrollHeight;
}

// ── Navigation ────────────────────────────────────────────────────────────────

type Section = 'overview' | 'ai-auditor' | 'entities' | 'compliance' | 'api-status' | 'ledger' | 'audit-logs';

function switchSection(target: Section): void {
  // Hide all sections
  document.querySelectorAll('.page-section').forEach((el) => el.classList.remove('active'));
  // Show target
  document.getElementById(`section-${target}`)?.classList.add('active');

  // Update sidebar active state
  document.querySelectorAll('.nav-item').forEach((el) => {
    el.classList.remove('active');
    el.classList.add('text-slate-400');
    el.classList.remove('text-[#a8a4ff]');
  });
  const activeNav = document.querySelector<HTMLElement>(`.nav-item[data-section="${target}"]`);
  if (activeNav) {
    activeNav.classList.add('active');
    activeNav.classList.remove('text-slate-400');
  }

  // Lazy-load section data
  if (target === 'entities') loadEntities();
  if (target === 'compliance') loadCompliance();
  if (target === 'api-status') loadApiStatus();
  if (target === 'ai-auditor') loadReports();
  if (target === 'ledger') loadLedger();
  if (target === 'audit-logs') loadAuditLogs();
}

// ── Overview / Dashboard data ─────────────────────────────────────────────────

async function loadDashboard(): Promise<void> {
  try {
    const data: DashboardResponse = await api.dashboard();

    setText('stat-invoices', fmt(data.run_summary.invoices_processed));
    setText('stat-value', fmtUsd(data.run_summary.total_invoice_value_usd));
    setText('stat-critical', fmt(data.severity_breakdown.critical));
    setText('stat-high', fmt(data.severity_breakdown.high));

    const total =
      (data.severity_breakdown.critical ?? 0) +
      (data.severity_breakdown.high ?? 0) +
      (data.severity_breakdown.medium ?? 0) +
      (data.severity_breakdown.low ?? 0);

    if (total > 0) {
      const pct = (n: number) => Math.round((n / total) * 100);
      setText('sev-critical-pct', `${pct(data.severity_breakdown.critical)}%`);
      setText('sev-high-pct', `${pct(data.severity_breakdown.high)}%`);
      setText('sev-low-pct', `${pct(data.severity_breakdown.low + data.severity_breakdown.medium)}%`);
      setText('sev-total', fmt(total));
      updateDonut(pct(data.severity_breakdown.critical), pct(data.severity_breakdown.high), pct(data.severity_breakdown.medium + data.severity_breakdown.low));
    }

    renderVendors(data.top_vendors_by_spend);
    renderOverviewInvoices(data.per_invoice_summary);

    // Also push to compliance section tables
    renderRoutes(data.most_overpriced_routes);
    renderAnomalyTypes(data.top_anomaly_types);
    renderComplianceInvoices(data.per_invoice_summary);
  } catch (err) {
    console.error('Dashboard load failed:', err);
  }
}

function updateDonut(critPct: number, highPct: number, lowPct: number): void {
  const C = 2 * Math.PI * 16;
  const set = (id: string, pct: number, offset: number) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.setAttribute('stroke-dasharray', `${((pct / 100) * C).toFixed(1)}, ${C.toFixed(1)}`);
    el.setAttribute('stroke-dashoffset', String(-(offset / 100) * C));
  };
  set('donut-critical', critPct, 0);
  set('donut-high', highPct, critPct);
  set('donut-low', lowPct, critPct + highPct);
}

function renderVendors(vendors: Record<string, number>): void {
  const container = document.getElementById('vendors-list');
  if (!container) return;
  const entries = Object.entries(vendors).sort(([, a], [, b]) => b - a).slice(0, 5);
  if (entries.length === 0) {
    container.innerHTML = '<p class="text-slate-500 text-xs font-mono">No vendor data yet. Run the pipeline first.</p>';
    return;
  }
  const max = entries[0][1];
  container.innerHTML = entries
    .map(([name, amount], i) => `
      <div class="space-y-2">
        <div class="flex justify-between text-xs font-mono text-slate-400">
          <span>${name}</span><span>${fmtUsd(amount)}</span>
        </div>
        <div class="w-full bg-surface-container-highest h-2 rounded-full overflow-hidden">
          <div class="bg-primary h-full rounded-full transition-all duration-700"
               style="width:${Math.round((amount / max) * 100)}%;opacity:${1 - i * 0.15}"></div>
        </div>
      </div>`)
    .join('');
}

function renderOverviewInvoices(rows: DashboardResponse['per_invoice_summary']): void {
  const tbody = document.getElementById('invoice-tbody');
  if (!tbody) return;
  if (!rows || rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="px-8 py-6 text-slate-500 text-xs font-mono text-center">No invoices yet — run the pipeline in AI Auditor.</td></tr>`;
    return;
  }
  const seen = new Set<string>();
  const unique = rows.filter((r) => { if (seen.has(r.invoice_number)) return false; seen.add(r.invoice_number); return true; });
  tbody.innerHTML = unique.slice(0, 5).map((inv) => `
    <tr class="hover:bg-white/[0.02] transition-colors">
      <td class="px-8 py-6 font-mono text-sm text-on-surface">${inv.invoice_number ?? '—'}</td>
      <td class="px-8 py-6">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-[10px] font-bold">
            ${(inv.vendor_name ?? '??').substring(0, 2).toUpperCase()}
          </div>
          <span class="text-sm font-semibold">${inv.vendor_name ?? '—'}</span>
        </div>
      </td>
      <td class="px-8 py-6 text-sm text-slate-400">${inv.invoice_date ?? '—'}</td>
      <td class="px-8 py-6 font-mono text-sm font-bold">${fmtUsd(inv.total_amount)}</td>
      <td class="px-8 py-6">${severityBadge(inv.severity)}</td>
      <td class="px-8 py-6 text-right">
        <button class="px-4 py-2 bg-surface-container-highest rounded-lg text-xs font-bold hover:bg-primary hover:text-on-primary transition-all" data-nav="entities">View All</button>
      </td>
    </tr>`).join('');
}

// ── Compliance section ────────────────────────────────────────────────────────

function renderRoutes(routes: Record<string, { standard: number; charged: number; delta_pct: number }>): void {
  const tbody = document.getElementById('routes-tbody');
  if (!tbody) return;
  const entries = Object.entries(routes).sort(([, a], [, b]) => b.delta_pct - a.delta_pct).slice(0, 8);
  if (entries.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="px-6 py-4 text-slate-500 text-xs font-mono">No overpriced routes detected.</td></tr>`;
    return;
  }
  tbody.innerHTML = entries.map(([route, d]) => `
    <tr>
      <td class="px-6 py-4 font-mono text-xs">${route}</td>
      <td class="px-6 py-4 text-slate-400 font-mono text-xs">${fmtUsd(d.standard)}</td>
      <td class="px-6 py-4 text-error font-bold font-mono text-xs">${fmtUsd(d.charged)}</td>
      <td class="px-6 py-4 text-error font-mono text-xs">+${Math.round(d.delta_pct)}%</td>
    </tr>`).join('');
}

function renderAnomalyTypes(types: Record<string, number>): void {
  const tbody = document.getElementById('anomaly-tbody');
  if (!tbody) return;
  const entries = Object.entries(types).sort(([, a], [, b]) => b - a).slice(0, 8);
  if (entries.length === 0) {
    tbody.innerHTML = `<tr><td colspan="3" class="px-6 py-4 text-slate-500 text-xs font-mono">No anomalies detected.</td></tr>`;
    return;
  }
  tbody.innerHTML = entries.map(([name, count]) => `
    <tr>
      <td class="px-6 py-4 font-bold text-on-surface text-xs">${name}</td>
      <td class="px-6 py-4 font-mono text-xs">${String(count).padStart(2, '0')}</td>
      <td class="px-6 py-4">
        <span class="px-2 py-1 bg-primary/10 text-primary rounded text-[10px] uppercase font-bold">Detected</span>
      </td>
    </tr>`).join('');
}

function renderComplianceInvoices(rows: DashboardResponse['per_invoice_summary']): void {
  const tbody = document.getElementById('compliance-invoice-tbody');
  if (!tbody) return;
  if (!rows || rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="px-8 py-6 text-slate-500 text-xs font-mono text-center">No data yet.</td></tr>`;
    return;
  }
  const seen = new Set<string>();
  const unique = rows.filter((r) => { if (seen.has(r.invoice_number)) return false; seen.add(r.invoice_number); return true; });
  tbody.innerHTML = unique.map((inv) => `
    <tr class="hover:bg-white/[0.02] transition-colors">
      <td class="px-8 py-5 font-mono text-sm">${inv.invoice_number ?? '—'}</td>
      <td class="px-8 py-5 text-sm">${inv.vendor_name ?? '—'}</td>
      <td class="px-8 py-5 text-sm text-slate-400">${inv.invoice_date ?? '—'}</td>
      <td class="px-8 py-5 font-mono text-sm font-bold">${fmtUsd(inv.total_amount)}</td>
      <td class="px-8 py-5">${severityBadge(inv.severity)}</td>
      <td class="px-8 py-5 font-mono text-sm">${inv.anomaly_count ?? 0}</td>
    </tr>`).join('');
}

async function loadCompliance(): Promise<void> {
  // Data already loaded by loadDashboard — just a no-op trigger
  try {
    const data = await api.dashboard();
    renderRoutes(data.most_overpriced_routes);
    renderAnomalyTypes(data.top_anomaly_types);
    renderComplianceInvoices(data.per_invoice_summary);
  } catch { /* silent */ }
}

// ── Entities section ──────────────────────────────────────────────────────────

let currentPage = 1;

async function loadEntities(page = currentPage): Promise<void> {
  currentPage = page;
  setText('page-indicator', `Page ${page}`);
  const tbody = document.getElementById('entities-tbody');
  if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="px-8 py-6 text-slate-500 text-xs font-mono text-center animate-pulse">Loading…</td></tr>`;

  try {
    const data = await api.invoices(page, 20);

    const prev = document.getElementById('prev-page-btn') as HTMLButtonElement | null;
    const next = document.getElementById('next-page-btn') as HTMLButtonElement | null;
    if (prev) prev.disabled = page <= 1;
    if (next) next.disabled = !data.has_next;

    if (!tbody) return;
    if (data.invoices.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="px-8 py-6 text-slate-500 text-xs font-mono text-center">No invoices in DB yet. Run the pipeline first.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.invoices.map((inv: Invoice) => `
      <tr class="hover:bg-white/[0.02] transition-colors">
        <td class="px-8 py-5 font-mono text-sm text-on-surface">${inv.invoice_number ?? '—'}</td>
        <td class="px-8 py-5 text-sm font-semibold">${inv.vendor_name ?? '—'}</td>
        <td class="px-8 py-5 text-sm text-slate-400">${inv.invoice_date ?? '—'}</td>
        <td class="px-8 py-5 font-mono text-sm font-bold">${fmtUsd(inv.total_amount)}</td>
        <td class="px-8 py-5 font-mono text-sm">${inv.currency ?? '—'}</td>
        <td class="px-8 py-5">${severityBadge(inv.status ?? '')}</td>
        <td class="px-8 py-5 text-right">
          <button
            class="px-4 py-2 bg-surface-container-highest rounded-lg text-xs font-bold hover:bg-primary hover:text-on-primary transition-all view-inv-btn"
            data-id="${inv.id}"
          >View</button>
        </td>
      </tr>`).join('');

    // Wire view buttons
    tbody.querySelectorAll<HTMLButtonElement>('.view-inv-btn').forEach((btn) => {
      btn.addEventListener('click', () => loadInvoiceDetail(Number(btn.dataset.id)));
    });
  } catch (err) {
    console.error('Entities load failed:', err);
  }
}

async function loadInvoiceDetail(id: number): Promise<void> {
  const detail = document.getElementById('invoice-detail');
  const json = document.getElementById('invoice-detail-json');
  if (!detail || !json) return;
  json.textContent = 'Loading…';
  detail.classList.remove('hidden');
  detail.scrollIntoView({ behavior: 'smooth' });
  try {
    const data = await api.invoice(id);
    json.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    json.textContent = `Error: ${err}`;
  }
}

// ── API Status section ────────────────────────────────────────────────────────

async function loadApiStatus(): Promise<void> {
  try {
    const [health, status] = await Promise.all([api.health(), api.status()]);

    // Health
    const dot = document.getElementById('health-dot');
    if (dot) dot.className = 'w-3 h-3 rounded-full bg-tertiary-fixed';
    setText('health-status', `OK — ${health.status}`);
    setText('health-timestamp', health.timestamp);

    // Groq
    const groqDot = document.getElementById('groq-dot');
    if (groqDot) groqDot.className = `w-3 h-3 rounded-full ${status.groq_configured ? 'bg-tertiary-fixed' : 'bg-error'}`;
    setText('groq-status', status.groq_configured ? 'Configured' : 'Missing Key');

    // Apify
    const apifyDot = document.getElementById('apify-dot');
    if (apifyDot) apifyDot.className = `w-3 h-3 rounded-full ${status.apify_configured ? 'bg-tertiary-fixed' : 'bg-yellow-400'}`;
    setText('apify-status', status.apify_configured ? 'Configured' : 'Not Set');
    setText('apify-mode', status.mock_mode ? 'Mock mode (demo rates)' : 'Live Apify scraping');

    // Pipeline
    setText('pipeline-status-api', status.pipeline_status.toUpperCase());

    // DB
    setText('db-url', status.database_url);
    setText('db-invoices', String(status.invoices_in_db));
    setText('db-feedback', String(status.feedback_corrections));

    // FS
    setText('fs-pdfs', String(status.input_pdfs));
    setText('fs-reports', String(status.reports_generated));
  } catch (err) {
    setText('health-status', `Unreachable — ${err}`);
    const dot = document.getElementById('health-dot');
    if (dot) dot.className = 'w-3 h-3 rounded-full bg-error';
  }
}

// ── Reports (in AI Auditor section) ─────────────────────────────────────────

async function loadReports(): Promise<void> {
  const container = document.getElementById('reports-list');
  if (!container) return;
  try {
    const data = await api.reports();
    if (data.reports.length === 0) {
      container.innerHTML = `<p class="text-slate-500 text-xs font-mono">No reports yet.</p>`;
      return;
    }
    container.innerHTML = data.reports.slice(0, 5).map((r) => `
      <div class="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
        <div>
          <p class="text-xs font-mono text-on-surface truncate max-w-[160px]">${r.filename}</p>
          <p class="text-[10px] text-slate-500">${Math.round(r.size_bytes / 1024)}KB · ${new Date(r.modified_at).toLocaleString()}</p>
        </div>
        <button
          class="px-3 py-1 bg-surface-container-highest rounded text-xs font-bold text-slate-300 hover:bg-primary hover:text-on-primary transition-all view-report-btn"
          data-filename="${r.filename}"
        >JSON</button>
      </div>`).join('');

    container.querySelectorAll<HTMLButtonElement>('.view-report-btn').forEach((btn) => {
      btn.addEventListener('click', async () => {
        try {
          const json = await api.report(btn.dataset.filename!);
          const win = window.open('', '_blank');
          if (win) win.document.write(`<pre style="background:#0e0e13;color:#a8a4ff;font-family:JetBrains Mono,monospace;padding:2rem;white-space:pre-wrap">${JSON.stringify(json, null, 2)}</pre>`);
        } catch (err) { alert(`Failed: ${err}`); }
      });
    });
  } catch (err) {
    console.error('Reports load failed:', err);
  }
}

// ── Pipeline ──────────────────────────────────────────────────────────────────

let pipelineEs: EventSource | null = null;

function updatePipelineStatus(state: PipelineState): void {
  const dot = document.getElementById('pipeline-status-dot');
  const txt = document.getElementById('pipeline-status-text');
  const bar = document.getElementById('pipeline-progress-bar');
  const pct = document.getElementById('pipeline-progress-pct');
  const lbl = document.getElementById('pipeline-progress-label');

  if (dot) dot.className = `w-2 h-2 rounded-full transition-all ${state.status === 'running' ? 'bg-error animate-ping' : state.status === 'completed' ? 'bg-tertiary-fixed' : 'bg-slate-500'}`;
  if (txt) txt.textContent = state.status.toUpperCase();
  if (bar) bar.style.width = state.status === 'completed' ? '100%' : state.status === 'running' ? '65%' : '0%';
  if (pct) pct.textContent = state.status === 'completed' ? '100% Complete' : state.status === 'running' ? 'Processing…' : 'Idle';
  if (lbl) lbl.textContent = state.status === 'running' ? 'Processing Invoices' : state.status === 'completed' ? 'Pipeline Complete' : 'Awaiting Input';
}

async function startPipeline(): Promise<void> {
  // Switch to AI Auditor section so user can see the logs
  switchSection('ai-auditor');

  const runBtn = document.getElementById('run-pipeline-btn') as HTMLButtonElement | null;
  if (runBtn) runBtn.disabled = true;
  appendLog('Triggering audit pipeline…', 'text-primary-dim');

  try {
    await api.pipelineRun();
    appendLog('Pipeline started. Streaming live logs…', 'text-tertiary-fixed-dim');

    if (pipelineEs) pipelineEs.close();
    pipelineEs = api.pipelineStream();

    pipelineEs.onmessage = (e) => {
      try {
        const item = JSON.parse(e.data) as { message: string };
        const cls = item.message.startsWith('ERROR') ? 'text-error'
          : item.message.includes('complete') ? 'text-tertiary-fixed-dim'
          : item.message.includes('ANOMALY') || item.message.includes('WARNING') ? 'text-primary-dim'
          : 'text-slate-500';
        appendLog(item.message, cls);

        if (item.message.includes('Pipeline complete') || item.message.startsWith('ERROR')) {
          pipelineEs?.close();
          if (runBtn) runBtn.disabled = false;
          appendLog('Refreshing dashboard data…', 'text-tertiary-fixed-dim');
          Promise.all([loadDashboard(), loadReports()]).then(() => {
            appendLog('Dashboard updated.', 'text-tertiary-fixed');
          });
        }
      } catch { /* ignore */ }
    };

    pipelineEs.onerror = () => {
      appendLog('Stream connection lost.', 'text-error');
      pipelineEs?.close();
      if (runBtn) runBtn.disabled = false;
    };
  } catch (err) {
    appendLog(`Failed to start: ${err}`, 'text-error');
    if (runBtn) runBtn.disabled = false;
  }
}

// ── File upload ───────────────────────────────────────────────────────────────

function setupUpload(): void {
  const zone = document.getElementById('upload-zone');
  const fileInput = document.getElementById('file-input') as HTMLInputElement | null;

  if (!zone) return;

  zone.addEventListener('click', () => fileInput?.click());
  zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('border-primary/50'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('border-primary/50'));
  zone.addEventListener('drop', async (e) => {
    e.preventDefault();
    zone.classList.remove('border-primary/50');
    if (e.dataTransfer?.files.length) await uploadFiles(e.dataTransfer.files);
  });
  fileInput?.addEventListener('change', async () => {
    if (fileInput.files?.length) await uploadFiles(fileInput.files);
  });
}

async function uploadFiles(files: FileList): Promise<void> {
  const pdfs = Array.from(files).filter((f) => f.name.toLowerCase().endsWith('.pdf'));
  if (pdfs.length === 0) { appendLog('Only PDF files accepted.', 'text-error'); return; }

  appendLog(`Uploading ${pdfs.length} PDF(s): ${pdfs.map((f) => f.name).join(', ')}`, 'text-primary-dim');
  try {
    const res = await api.upload(pdfs);
    appendLog(`Uploaded ${res.count} file(s): ${res.uploaded.join(', ')}`, 'text-tertiary-fixed-dim');
    appendLog('Files ready. Click "Run Audit Pipeline" to process them.', 'text-slate-400');

    // Update file list UI
    const uploaded = document.getElementById('uploaded-files');
    const list = document.getElementById('file-list');
    if (uploaded && list) {
      uploaded.classList.remove('hidden');
      list.innerHTML = res.uploaded.map((f) => `
        <div class="flex items-center gap-2 text-xs font-mono">
          <span class="material-symbols-outlined text-tertiary-fixed text-sm">check_circle</span>
          <span class="text-on-surface">${f}</span>
        </div>`).join('');
    }

    // Refresh stats
    api.status().then((s) => {
      setText('stat-pdfs', String(s.input_pdfs));
      setText('stat-pdfs-2', String(s.input_pdfs));
    }).catch(() => {});
  } catch (err) {
    appendLog(`Upload failed: ${err}`, 'text-error');
  }
}

// ── Ledger ────────────────────────────────────────────────────────────────────

async function loadLedger(): Promise<void> {
  const tbody = document.getElementById('ledger-tbody');
  if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="px-6 py-8 text-slate-500 text-xs text-center animate-pulse">Loading ledger…</td></tr>`;

  try {
    const data = await api.invoices(1, 100);
    const invoices = data.invoices;

    if (!tbody) return;
    if (invoices.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" class="px-6 py-8 text-slate-500 text-xs text-center">No invoices yet. Run the pipeline first.</td></tr>`;
      setText('ledger-total-debit', '—');
      setText('ledger-total-credit', '—');
      setText('ledger-net', '—');
      setText('ledger-row-count', '0 entries');
      return;
    }

    let totalDebit = 0;
    let totalCredit = 0;

    tbody.innerHTML = invoices.map((inv: Invoice, i: number) => {
      const amount = inv.total_amount ?? 0;
      // Credit for normal invoices, debit for anomalous (overpriced)
      const isAnomalous = (inv.status ?? '').toLowerCase() === 'critical' || (inv.status ?? '').toLowerCase() === 'high';
      const debit = isAnomalous ? amount : 0;
      const credit = isAnomalous ? 0 : amount;
      totalDebit += debit;
      totalCredit += credit;

      const debitCell = debit > 0
        ? `<td class="px-6 py-4 text-error font-bold">${fmtUsd(debit)}</td>`
        : `<td class="px-6 py-4 text-slate-600">—</td>`;
      const creditCell = credit > 0
        ? `<td class="px-6 py-4 text-tertiary-fixed font-bold">${fmtUsd(credit)}</td>`
        : `<td class="px-6 py-4 text-slate-600">—</td>`;

      return `
        <tr class="hover:bg-white/[0.02] transition-colors">
          <td class="px-6 py-4 text-slate-500 text-[10px]">${String(i + 1).padStart(4, '0')}</td>
          <td class="px-6 py-4 text-slate-400">${inv.invoice_date ?? '—'}</td>
          <td class="px-6 py-4 font-semibold text-on-surface text-xs">
            <div class="flex items-center gap-2">
              <div class="w-6 h-6 rounded-full bg-slate-800 flex items-center justify-center text-[9px] font-bold shrink-0">
                ${(inv.vendor_name ?? '??').substring(0, 2).toUpperCase()}
              </div>
              <span class="truncate max-w-[120px]">${inv.vendor_name ?? '—'}</span>
            </div>
          </td>
          <td class="px-6 py-4 text-slate-300">${inv.invoice_number ?? '—'}</td>
          <td class="px-6 py-4 text-slate-400">${inv.incoterms ?? '—'}</td>
          <td class="px-6 py-4 text-slate-400">${inv.currency ?? 'USD'}</td>
          ${debitCell}
          ${creditCell}
          <td class="px-6 py-4">${severityBadge(inv.status ?? '')}</td>
        </tr>`;
    }).join('');

    const net = totalCredit - totalDebit;
    setText('ledger-total-debit', fmtUsd(totalDebit));
    setText('ledger-total-credit', fmtUsd(totalCredit));
    const netEl = document.getElementById('ledger-net');
    if (netEl) {
      netEl.textContent = (net >= 0 ? '+' : '') + fmtUsd(Math.abs(net));
      netEl.className = `text-2xl font-mono font-bold ${net >= 0 ? 'text-tertiary-fixed' : 'text-error'}`;
    }
    setText('ledger-row-count', `${invoices.length} entries`);
  } catch (err) {
    console.error('Ledger load failed:', err);
    const tbody2 = document.getElementById('ledger-tbody');
    if (tbody2) tbody2.innerHTML = `<tr><td colspan="9" class="px-6 py-8 text-error text-xs text-center">Failed to load ledger: ${err}</td></tr>`;
  }
}

// ── Audit Logs ────────────────────────────────────────────────────────────────

async function loadAuditLogs(): Promise<void> {
  try {
    const [feedbackData, pipelineState] = await Promise.all([
      api.feedback(),
      api.pipelineStatus(),
    ]);

    // Corrections table
    const tbody = document.getElementById('audit-logs-tbody');
    setText('audit-total-corrections', `${feedbackData.total} total`);

    if (tbody) {
      if (feedbackData.entries.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="px-6 py-8 text-slate-500 text-center">No corrections yet.</td></tr>`;
      } else {
        tbody.innerHTML = feedbackData.entries.map((entry: FeedbackEntry) => `
          <tr class="hover:bg-white/[0.02] transition-colors">
            <td class="px-6 py-3 text-slate-500">${entry.id}</td>
            <td class="px-6 py-3 text-primary">#${entry.invoice_id}</td>
            <td class="px-6 py-3 font-bold text-on-surface">${entry.field_name}</td>
            <td class="px-6 py-3 text-error line-through opacity-60 max-w-[100px] truncate">${entry.original_value || '—'}</td>
            <td class="px-6 py-3 text-tertiary-fixed max-w-[100px] truncate">${entry.corrected_value || '—'}</td>
            <td class="px-6 py-3 text-slate-400 max-w-[120px] truncate">${entry.notes ?? '—'}</td>
            <td class="px-6 py-3 text-slate-500">${new Date(entry.created_at).toLocaleDateString()}</td>
          </tr>`).join('');
      }
    }

    // Top correction fields chart
    const chart = document.getElementById('audit-correction-chart');
    if (chart) {
      const entries = Object.entries(feedbackData.most_common_corrections).sort(([, a], [, b]) => b - a).slice(0, 6);
      if (entries.length === 0) {
        chart.innerHTML = `<p class="text-slate-500 text-xs font-mono">No correction data yet.</p>`;
      } else {
        const max = entries[0][1];
        chart.innerHTML = entries.map(([field, count]) => `
          <div class="space-y-1">
            <div class="flex justify-between text-xs font-mono text-slate-400">
              <span>${field}</span><span class="text-primary">${count}</span>
            </div>
            <div class="w-full bg-surface-container-highest h-1.5 rounded-full overflow-hidden">
              <div class="bg-primary h-full rounded-full" style="width:${Math.round((count / max) * 100)}%"></div>
            </div>
          </div>`).join('');
      }
    }

    // Pipeline state panel
    const stateEl = document.getElementById('audit-pipeline-state');
    if (stateEl) {
      const statusColor = pipelineState.status === 'running' ? 'text-primary' : pipelineState.status === 'completed' ? 'text-tertiary-fixed' : pipelineState.status === 'failed' ? 'text-error' : 'text-slate-400';
      stateEl.innerHTML = `
        <div class="grid grid-cols-2 gap-4">
          <div>
            <span class="text-slate-500">Status</span>
            <p class="font-bold ${statusColor} uppercase mt-1">${pipelineState.status}</p>
          </div>
          <div>
            <span class="text-slate-500">Started</span>
            <p class="text-on-surface mt-1">${pipelineState.started_at ? new Date(pipelineState.started_at).toLocaleString() : '—'}</p>
          </div>
          <div>
            <span class="text-slate-500">Completed</span>
            <p class="text-on-surface mt-1">${pipelineState.completed_at ? new Date(pipelineState.completed_at).toLocaleString() : '—'}</p>
          </div>
          <div>
            <span class="text-slate-500">Last Error</span>
            <p class="text-error mt-1">${pipelineState.error ?? '—'}</p>
          </div>
        </div>
        ${pipelineState.last_result ? `
        <div class="mt-4 pt-4 border-t border-white/5">
          <p class="text-slate-500 mb-2">Last Result</p>
          <pre class="text-[10px] text-on-surface-variant bg-surface-container-lowest p-3 rounded-lg overflow-x-auto whitespace-pre-wrap max-h-40 no-scrollbar">${JSON.stringify(pipelineState.last_result, null, 2)}</pre>
        </div>` : ''}`;
    }
  } catch (err) {
    console.error('Audit logs load failed:', err);
  }
}

// ── Settings Panel ────────────────────────────────────────────────────────────

function openSettings(): void {
  const panel = document.getElementById('settings-panel');
  const overlay = document.getElementById('settings-overlay');
  panel?.classList.add('open');
  overlay?.classList.remove('hidden');

  // Populate with live data
  api.status().then((s: StatusResponse) => {
    const groqDot = document.getElementById('sp-groq-dot');
    if (groqDot) groqDot.className = `w-2.5 h-2.5 rounded-full ${s.groq_configured ? 'bg-tertiary-fixed' : 'bg-error'}`;
    setText('sp-groq-status', s.groq_configured ? 'Configured ✓' : 'Missing Key ✗');

    const apifyDot = document.getElementById('sp-apify-dot');
    if (apifyDot) apifyDot.className = `w-2.5 h-2.5 rounded-full ${s.apify_configured ? 'bg-tertiary-fixed' : 'bg-yellow-400'}`;
    setText('sp-apify-status', s.apify_configured ? 'Configured ✓' : 'Not Set');

    const mockEl = document.getElementById('sp-mock-mode');
    if (mockEl) {
      mockEl.textContent = s.mock_mode ? 'Enabled' : 'Disabled';
      mockEl.className = `px-3 py-1 rounded-full text-[10px] font-bold font-mono uppercase ${s.mock_mode ? 'bg-yellow-500/20 text-yellow-300' : 'bg-tertiary-fixed/20 text-tertiary-fixed'}`;
    }

    setText('sp-pipeline-status', s.pipeline_status.toUpperCase());
    setText('sp-invoices', String(s.invoices_in_db));
    setText('sp-feedback', String(s.feedback_corrections));
    setText('sp-db-url', s.database_url);
  }).catch(() => {});
}

function closeSettings(): void {
  document.getElementById('settings-panel')?.classList.remove('open');
  document.getElementById('settings-overlay')?.classList.add('hidden');
}

// ── Notifications ─────────────────────────────────────────────────────────────

let notifOpen = false;

function toggleNotifications(): void {
  const dropdown = document.getElementById('notif-dropdown');
  if (!dropdown) return;
  notifOpen = !notifOpen;
  if (notifOpen) {
    dropdown.classList.add('open');
    loadNotifications();
  } else {
    dropdown.classList.remove('open');
  }
}

async function loadNotifications(): Promise<void> {
  const list = document.getElementById('notif-list');
  const countEl = document.getElementById('notif-count');
  if (!list) return;

  try {
    const [dashData, pipelineState] = await Promise.all([
      api.dashboard(),
      api.pipelineStatus(),
    ]);

    const events: Array<{ icon: string; iconClass: string; title: string; sub: string }> = [];

    // Pipeline state event
    events.push({
      icon: pipelineState.status === 'running' ? 'sync' : pipelineState.status === 'completed' ? 'check_circle' : 'radio_button_unchecked',
      iconClass: pipelineState.status === 'running' ? 'text-primary' : pipelineState.status === 'completed' ? 'text-tertiary-fixed' : 'text-slate-500',
      title: `Pipeline ${pipelineState.status.toUpperCase()}`,
      sub: pipelineState.completed_at ? `Completed ${new Date(pipelineState.completed_at).toLocaleTimeString()}` : 'No recent run',
    });

    // Critical anomalies
    const critCount = dashData.severity_breakdown.critical ?? 0;
    if (critCount > 0) {
      events.push({
        icon: 'warning',
        iconClass: 'text-error',
        title: `${critCount} Critical Anomaly${critCount > 1 ? 'ies' : ''}`,
        sub: 'Immediate review required',
      });
    }

    // Top anomaly types (up to 3)
    Object.entries(dashData.top_anomaly_types).slice(0, 3).forEach(([name, count]) => {
      events.push({
        icon: 'bug_report',
        iconClass: 'text-primary',
        title: name,
        sub: `${count} occurrence${count > 1 ? 's' : ''} detected`,
      });
    });

    // Invoice count
    events.push({
      icon: 'description',
      iconClass: 'text-slate-400',
      title: `${dashData.run_summary.invoices_processed} Invoices Processed`,
      sub: `Total value: ${fmtUsd(dashData.run_summary.total_invoice_value_usd)}`,
    });

    const displayEvents = events.slice(0, 5);
    if (countEl) countEl.textContent = `${displayEvents.length} events`;

    list.innerHTML = displayEvents.map((ev) => `
      <div class="px-5 py-3 flex items-start gap-3 hover:bg-white/[0.03] transition-colors">
        <span class="material-symbols-outlined text-base mt-0.5 ${ev.iconClass}">${ev.icon}</span>
        <div>
          <p class="text-xs font-semibold text-on-surface">${ev.title}</p>
          <p class="text-[10px] text-slate-500 font-mono mt-0.5">${ev.sub}</p>
        </div>
      </div>`).join('');
  } catch {
    list.innerHTML = `<p class="px-5 py-4 text-xs text-error font-mono">Failed to load events.</p>`;
  }
}

// ── Help Chatbot ──────────────────────────────────────────────────────────────

let chatOpen = false;
let chatUnread = 0;

function openChat(): void {
  chatOpen = true;
  const win = document.getElementById('chat-window');
  if (win) {
    win.style.opacity = '1';
    win.style.transform = 'scale(1) translateY(0)';
    win.style.pointerEvents = 'auto';
  }
  const icon = document.getElementById('chat-toggle-icon');
  if (icon) icon.textContent = 'close';
  chatUnread = 0;
  updateChatBadge();
  setTimeout(() => (document.getElementById('chat-input') as HTMLInputElement | null)?.focus(), 150);
}

function closeChat(): void {
  chatOpen = false;
  const win = document.getElementById('chat-window');
  if (win) {
    win.style.opacity = '0';
    win.style.transform = 'scale(0.9) translateY(20px)';
    win.style.pointerEvents = 'none';
  }
  const icon = document.getElementById('chat-toggle-icon');
  if (icon) icon.textContent = 'chat';
}

function clearChat(): void {
  const msgs = document.getElementById('chat-messages');
  if (msgs) msgs.innerHTML = '';
  document.getElementById('chat-faq-chips')?.classList.remove('hidden');
  addBotMessage("Chat cleared. How can I help you?");
}

function updateChatBadge(): void {
  const badge = document.getElementById('chat-unread-badge');
  if (!badge) return;
  if (chatUnread > 0 && !chatOpen) {
    badge.textContent = String(chatUnread);
    badge.classList.remove('hidden');
  } else {
    badge.classList.add('hidden');
  }
}

function addBotMessage(html: string): void {
  const msgs = document.getElementById('chat-messages');
  if (!msgs) return;
  const div = document.createElement('div');
  div.className = 'flex gap-2 items-start';
  div.innerHTML = `
    <div class="w-6 h-6 rounded-full bg-primary/20 border border-primary/40 flex items-center justify-center flex-shrink-0 mt-0.5" style="font-size:9px;color:#a8a4ff">AI</div>
    <div class="rounded-2xl rounded-tl-sm px-3 py-2 text-xs text-slate-200 leading-relaxed" style="background:#1e1e28;max-width:82%">${html}</div>
  `;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  if (!chatOpen) {
    chatUnread++;
    updateChatBadge();
  }
}

function addUserMessage(text: string): void {
  const msgs = document.getElementById('chat-messages');
  if (!msgs) return;
  document.getElementById('chat-faq-chips')?.classList.add('hidden');
  const div = document.createElement('div');
  div.className = 'flex gap-2 items-start justify-end';
  div.innerHTML = `
    <div class="rounded-2xl rounded-tr-sm px-3 py-2 text-xs leading-relaxed" style="background:rgba(168,164,255,0.15);color:#c5c2ff;max-width:82%;border:1px solid rgba(168,164,255,0.2)">${text}</div>
  `;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

async function handleChatMessage(raw: string): Promise<void> {
  const text = raw.trim();
  if (!text) return;
  addUserMessage(text);
  const cmd = text.toLowerCase();

  // What is this / about
  if (cmd.includes('what is this') || cmd.includes('what is cpa') || cmd.includes('about') || cmd === 'overview') {
    addBotMessage('CPA AI Agent is an intelligent invoice auditing system. It uses AI to extract data from PDF invoices, detect pricing anomalies, flag compliance issues, and generate detailed audit reports — automatically.');
    return;
  }

  // How to run audit / pipeline
  if (cmd.includes('how to run') || cmd.includes('run audit') || cmd.includes('start audit') || cmd.includes('run pipeline') || cmd.includes('start pipeline')) {
    addBotMessage('To run an audit:<br>1. Go to <b>AI Auditor</b> in the sidebar.<br>2. Upload PDF invoices via the upload area.<br>3. Click <b>Run Full Pipeline</b>.<br>Results appear in Entities and Ledger sections once complete.');
    return;
  }

  // Upload / PDF
  if (cmd.includes('upload') || cmd.includes('how to upload') || cmd.includes('pdf')) {
    addBotMessage('Go to the <b>AI Auditor</b> section and use the drag-and-drop area to upload PDF invoices. Multiple files supported. After uploading, click <b>Run Full Pipeline</b> to start analysis.');
    return;
  }

  // Anomalies
  if (cmd.includes('anomal') || cmd.includes('what are anomalies') || cmd.includes('what are flags')) {
    addBotMessage('Anomalies are irregularities detected in invoice data. Types include: overpriced routes, duplicate charges, missing required fields, currency mismatches, and amounts exceeding thresholds.<br><br>Severities: <b>Critical → High → Medium → Low</b>');
    return;
  }

  // Ledger
  if (cmd.includes('ledger') || cmd.includes('what is ledger') || cmd.includes('accounting')) {
    addBotMessage('The <b>Ledger</b> shows all extracted invoices in an accounting-style table — vendor, date, amount, currency, and audit status. Use it to review individual invoice records and track processing state.');
    return;
  }

  // Pipeline status
  if (cmd.includes('pipeline status') || cmd === 'pipeline') {
    try {
      const s = await api.pipelineStatus();
      const started = s.started_at ? ` Started: ${new Date(s.started_at).toLocaleTimeString()}` : '';
      const err = s.error ? `<br><span style="color:#ff6b6b">Error: ${s.error}</span>` : '';
      addBotMessage(`Pipeline is <b>${s.status}</b>.${started}${err}`);
    } catch {
      addBotMessage('Could not fetch pipeline status. Is the backend running?');
    }
    return;
  }

  // Invoice count
  if (cmd.includes('invoice count') || cmd.includes('how many') || cmd.includes('count invoices')) {
    try {
      const s = await api.status();
      addBotMessage(`<b>${s.invoices_in_db}</b> invoices in the database. <b>${s.reports_generated}</b> audit reports generated.`);
    } catch {
      addBotMessage('Could not reach the API. Check that the backend is running on port 8000.');
    }
    return;
  }

  // Critical anomalies
  if (cmd.includes('critical anomalies') || cmd.includes('critical flags') || cmd === 'critical') {
    try {
      const d = await api.dashboard();
      const crit = d.severity_breakdown.critical ?? 0;
      const high = d.severity_breakdown.high ?? 0;
      addBotMessage(`<b>${crit} critical</b> and <b>${high} high-severity</b> anomalies detected across processed invoices.`);
    } catch {
      addBotMessage('Could not fetch anomaly data from the dashboard.');
    }
    return;
  }

  // API status
  if (cmd === 'api status' || cmd === 'api') {
    try {
      const s = await api.status();
      const groq = s.groq_configured ? '✓' : '✗';
      const mock = s.mock_mode ? 'on' : 'off';
      addBotMessage(`API online. Groq: <b>${groq}</b> · Mock mode: <b>${mock}</b> · Pipeline: <b>${s.pipeline_status}</b> · Invoices: <b>${s.invoices_in_db}</b>`);
    } catch {
      addBotMessage('API appears to be unreachable. Check that the backend server is running.');
    }
    return;
  }

  // Navigate
  if (cmd.startsWith('go to ') || cmd.startsWith('goto ') || cmd.startsWith('navigate to ') || cmd.startsWith('open ')) {
    const target = cmd.replace(/^(go to |goto |navigate to |open )/, '').trim();
    const sectionMap: Record<string, Section> = {
      overview: 'overview', dashboard: 'overview', home: 'overview',
      auditor: 'ai-auditor', 'ai auditor': 'ai-auditor', pipeline: 'ai-auditor', audit: 'ai-auditor',
      entities: 'entities', invoices: 'entities',
      compliance: 'compliance',
      'api status': 'api-status', status: 'api-status', api: 'api-status',
      ledger: 'ledger',
      'audit logs': 'audit-logs', logs: 'audit-logs', 'audit log': 'audit-logs',
    };
    const section = sectionMap[target];
    if (section) {
      switchSection(section);
      addBotMessage(`Navigated to <b>${section}</b>.`);
    } else {
      addBotMessage(`Unknown section. Try: overview, auditor, entities, compliance, api status, ledger, or audit logs.`);
    }
    return;
  }

  // Clear cache
  if (cmd.includes('clear cache') || cmd === 'cache') {
    try {
      const res = await api.clearCache();
      addBotMessage(res.message);
    } catch {
      addBotMessage('Cache clear failed — check API connectivity.');
    }
    return;
  }

  // Help
  if (cmd === 'help' || cmd === '?') {
    addBotMessage('Things I can help with:<br>• What is this? / About<br>• How to run an audit<br>• How to upload PDF<br>• What are anomalies?<br>• What is Ledger?<br>• Invoice count<br>• Pipeline status<br>• API status<br>• Navigate (e.g. "go to ledger")');
    return;
  }

  // Fallback
  addBotMessage(`I'm not sure about that. Try: <i>"What is this?"</i>, <i>"How to run audit?"</i>, <i>"Invoice count"</i>, or <i>"API status"</i>.`);
}

// ── Status polling ────────────────────────────────────────────────────────────

function startStatusPolling(): void {
  const poll = async () => {
    try {
      const state = await api.pipelineStatus();
      updatePipelineStatus(state);
    } catch { /* silent */ }
  };
  poll();
  setInterval(poll, 5000);
}

// ── Boot ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  // Sidebar navigation
  document.querySelectorAll<HTMLElement>('.nav-item').forEach((item) => {
    item.addEventListener('click', () => {
      const section = item.dataset.section as Section;
      if (section) switchSection(section);
    });
  });

  // "View All →" buttons that nav to entities
  document.addEventListener('click', (e) => {
    const target = (e.target as HTMLElement).closest<HTMLElement>('[data-nav]');
    if (target?.dataset.nav) switchSection(target.dataset.nav as Section);
  });

  // Close invoice detail
  document.getElementById('close-detail-btn')?.addEventListener('click', () => {
    document.getElementById('invoice-detail')?.classList.add('hidden');
  });

  // Pagination
  document.getElementById('prev-page-btn')?.addEventListener('click', () => loadEntities(currentPage - 1));
  document.getElementById('next-page-btn')?.addEventListener('click', () => loadEntities(currentPage + 1));

  // Run pipeline buttons (header + sidebar "New Audit" + terminal button)
  const triggerPipeline = () => startPipeline();
  document.getElementById('run-pipeline-btn')?.addEventListener('click', triggerPipeline);
  document.getElementById('header-run-btn')?.addEventListener('click', triggerPipeline);
  document.getElementById('sidebar-run-btn')?.addEventListener('click', triggerPipeline);

  // Cancel
  document.getElementById('cancel-pipeline-btn')?.addEventListener('click', () => {
    pipelineEs?.close();
    appendLog('Pipeline stream disconnected by user.', 'text-slate-500');
    const btn = document.getElementById('run-pipeline-btn') as HTMLButtonElement | null;
    if (btn) btn.disabled = false;
  });

  // Clear cache
  document.getElementById('clear-cache-btn')?.addEventListener('click', async () => {
    try {
      const res = await api.clearCache();
      appendLog(res.message, 'text-tertiary-fixed-dim');
    } catch (err) {
      appendLog(`Cache clear failed: ${err}`, 'text-error');
    }
  });

  // Upload
  setupUpload();

  // Initial data loads
  loadDashboard();
  loadReports();
  startStatusPolling();

  // Initial system health check
  api.status().then((s) => {
    setText('stat-pdfs', String(s.input_pdfs));
    setText('stat-pdfs-2', String(s.input_pdfs));
    setText('stat-db-invoices', String(s.invoices_in_db));
    setText('stat-db-2', String(s.invoices_in_db));
    setText('stat-reports', String(s.reports_generated));
    setText('stat-feedback', String(s.feedback_corrections));

    const dot = document.getElementById('api-health-indicator');
    const txt = document.getElementById('api-health-text');
    if (dot) dot.className = 'w-2 h-2 rounded-full bg-tertiary-fixed animate-pulse';
    if (txt) txt.textContent = 'API Online';
  }).catch(() => {
    const dot = document.getElementById('api-health-indicator');
    const txt = document.getElementById('api-health-text');
    if (dot) dot.className = 'w-2 h-2 rounded-full bg-error';
    if (txt) txt.textContent = 'API Offline';
  });

  // Settings panel
  document.getElementById('settings-gear-btn')?.addEventListener('click', openSettings);
  document.getElementById('settings-close-btn')?.addEventListener('click', closeSettings);
  document.getElementById('settings-overlay')?.addEventListener('click', closeSettings);

  // Settings clear cache
  document.getElementById('sp-clear-cache-btn')?.addEventListener('click', async () => {
    const resultEl = document.getElementById('sp-cache-result');
    try {
      const res = await api.clearCache();
      if (resultEl) { resultEl.textContent = res.message; resultEl.classList.remove('hidden'); }
      appendLog(res.message, 'text-tertiary-fixed-dim');
    } catch (err) {
      if (resultEl) { resultEl.textContent = `Failed: ${err}`; resultEl.classList.remove('hidden'); }
    }
  });

  // Notifications bell
  document.getElementById('notif-bell-btn')?.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleNotifications();
  });

  // Close notifications on outside click
  document.addEventListener('click', (e) => {
    if (notifOpen) {
      const dropdown = document.getElementById('notif-dropdown');
      const bell = document.getElementById('notif-bell-btn');
      if (dropdown && !dropdown.contains(e.target as Node) && e.target !== bell) {
        notifOpen = false;
        dropdown.classList.remove('open');
      }
    }
  });

  // Ledger refresh button
  document.getElementById('ledger-refresh-btn')?.addEventListener('click', loadLedger);

  // Floating chat widget
  document.getElementById('chat-toggle-btn')?.addEventListener('click', () => {
    if (chatOpen) closeChat(); else openChat();
  });
  document.getElementById('chat-close-btn')?.addEventListener('click', closeChat);
  document.getElementById('chat-clear-btn')?.addEventListener('click', clearChat);

  const chatInput = document.getElementById('chat-input') as HTMLInputElement | null;

  const sendChatMessage = async () => {
    const val = chatInput?.value.trim() ?? '';
    if (!val) return;
    if (chatInput) chatInput.value = '';
    await handleChatMessage(val);
  };

  chatInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendChatMessage();
  });
  document.getElementById('chat-send-btn')?.addEventListener('click', sendChatMessage);

  document.querySelectorAll<HTMLButtonElement>('.faq-chip').forEach((chip) => {
    chip.addEventListener('click', async () => {
      if (!chatOpen) openChat();
      await handleChatMessage(chip.textContent?.trim() ?? '');
    });
  });

  // Welcome message
  addBotMessage("Hi! I'm the Sovereign Assistant. Ask me anything about this dashboard, or pick a question below.");

  // Boot log message
  appendLog('Sovereign Auditor online. System ready.', 'text-tertiary-fixed-dim opacity-80');
});
