// AgentBridge Dashboard Logic v6.2 - Manual Monitor + Behavioural Drift
const token = localStorage.getItem("token");
const org_id = localStorage.getItem("org_id");

if (!token && !window.location.pathname.endsWith("login.html") && !window.location.pathname.endsWith("signup.html")) {
    window.location.href = "login.html";
}

// --- CONSTANTS ---
const PERSONAS = {
    "fraud-detection": {
        name: "Fraud Bot",
        banner: "🤖 Active Agent: Fraud Bot — Transaction Compliance Mode",
        actions: ["approve", "reject", "verify"],
        actionLabels: {
            approve: "✅ Approved Transaction",
            reject: "❌ Rejected Transaction",
            verify: "🔎 Flagged for Verification"
        },
        icon: "🔍",
        fields: [
            { id: "amount", label: "Transaction Amount (₹)", type: "number", placeholder: "50000" },
            { id: "type", label: "Transaction Type", type: "select", options: ["UPI", "NEFT", "RTGS", "Wire"] },
            { id: "kyc_status", label: "KYC Status", type: "select", options: ["Verified", "Not Verified"] },
            { id: "is_pep", label: "Is PEP?", type: "select", options: ["No", "Yes"] },
            { id: "confidence", label: "Confidence Score (0-1)", type: "number", step: "0.1", value: "0.95" }
        ],
        clauses: ["3.1 (Decision Reasoning)", "6.1 (KYC for Approvals)", "4.4 (Session Identification)"]
    },
    "loan-approval": {
        name: "Loan Bot",
        banner: "💰 Active Agent: Loan Bot — Credit Risk Mode",
        actions: ["approve", "reject", "loan"],
        actionLabels: {
            approve: "✅ Loan Approved",
            reject: "❌ Loan Rejected",
            loan: "📋 Loan Under Review"
        },
        icon: "💰",
        fields: [
            { id: "loan_amount", label: "Loan Amount (₹)", type: "number", placeholder: "500000" },
            { id: "credit_score", label: "Credit Score (300-900)", type: "number", placeholder: "750" },
            { id: "income", label: "Annual Income (₹)", type: "number", placeholder: "1200000" },
            { id: "dti", label: "DTI Ratio", type: "number", step: "0.01", placeholder: "0.35" },
            { id: "employment", label: "Employment Years", type: "number", placeholder: "5" },
            { id: "kyc_status", label: "KYC Status", type: "select", options: ["Verified", "Not Verified"] },
            { id: "confidence", label: "Confidence Score (0-1)", type: "number", step: "0.1", value: "0.9" }
        ],
        clauses: ["3.1 (Reasoning)", "6.1 (KYC)", "5.2 (Action Classification)"]
    }
};

// Global State
let currentTab = "dashboard";
let agents = [];
let charts = {};
let driftData = null;

// --- INITIALIZATION ---
document.addEventListener("DOMContentLoaded", async () => {
    await loadInitialData();
    showTab("dashboard");
    
    if (!localStorage.getItem("onboarding_done")) {
        document.getElementById("onboarding-modal")?.classList.remove("hidden");
    }
});

async function loadInitialData() {
    await fetchProfile();
    await loadAgents();
    await loadStats();
}

// --- FETCHERS ---
async function apiFetch(url, options = {}) {
    const headers = {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json"
    };
    try {
        const res = await fetch(url, { ...options, headers });
        if (res.status === 401) {
            localStorage.removeItem("token");
            window.location.href = "login.html";
        }
        return await res.json();
    } catch (err) {
        console.error(`API Fetch Error [${url}]:`, err);
        return null;
    }
}

async function fetchProfile() {
    const data = await apiFetch("/api/settings/profile");
    if (data) {
        document.getElementById("company-name").innerText = data.name;
        document.getElementById("set-company-name").value = data.name;
        document.getElementById("set-industry").value = data.industry;
    }
}

async function loadAgents() {
    agents = await apiFetch("/api/agents/");
    if (!agents) return;
    
    // Fill selectors
    const selectors = ["agent-selector", "ml-agent-select"];
    selectors.forEach(sid => {
        const s = document.getElementById(sid);
        if (!s) return;
        const firstOption = (sid === "agent-selector") ? '<option value="all">All Agents</option>' : '';
        s.innerHTML = firstOption + agents.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
    });

    renderAgentTable();
}

async function loadStats() {
    const agentId = document.getElementById("agent-selector").value;
    const url = `/api/dashboard/stats?agent_id=${agentId}`;
    const data = await apiFetch(url);
    if (!data) return;

    document.getElementById("stat-logs").innerText = data.total_logs.toLocaleString();
    document.getElementById("stat-incidents").innerText = data.incidents.toLocaleString();
    document.getElementById("stat-risk").innerText = data.high_risk.toLocaleString();
    document.getElementById("stat-violations").innerText = data.violations.toLocaleString();
    document.getElementById("stat-latency").innerText = `${data.avg_latency}ms`;
    document.getElementById("stat-drift").innerText = data.drift_status?.charAt(0).toUpperCase() + data.drift_status?.slice(1) || "Stable";
    
    // Update Gauge
    const score = 84; 
    document.getElementById("compliance-score").innerText = score;
    const dashoffset = 502 - (502 * score / 100);
    document.getElementById("compliance-gauge").style.strokeDashoffset = dashoffset;

    await loadLogs(agentId);
}

// --- ENHANCED LOG FEED ---
async function loadLogs(agentId) {
    const url = `/api/logs?agent_id=${agentId}&limit=10`;
    const logs = await apiFetch(url);
    if (!logs) return;

    const tbody = document.getElementById("log-table-body");
    tbody.innerHTML = logs.map(l => {
        // Context-aware labels
        const agent = agents.find(a => a.id === l.agent_id);
        const typeKey = agent ? agent.agent_type : "fraud-detection";
        const meta = PERSONAS[typeKey] || PERSONAS["fraud-detection"];
        
        const actionLabel = meta.actionLabels[l.verdict] || l.verdict;
        const icon = meta.icon;
        
        // Formatted amount if available in input
        const input = typeof l.input === 'string' ? JSON.parse(l.input) : l.input;
        const amount = input.amount || input.loan_amount || null;
        const amountDisplay = amount ? `₹${Number(amount).toLocaleString()}` : "-";

        // Violation tag
        const violationBadge = l.violation_count > 0 ? `<span class="ml-2 px-1.5 py-0.5 bg-red-500/20 text-red-500 rounded text-[9px] font-black">⚠️ ${l.violation_count}</span>` : '';

        return `
            <tr class="hover:bg-white/5 transition-all group">
                <td class="px-6 py-4 font-mono text-[11px] text-gray-500">${l.decision_id}</td>
                <td class="px-6 py-4 text-[11px] text-gray-500" title="${new Date(l.created_at).toLocaleString()}">${timeAgo(l.created_at)}</td>
                <td class="px-6 py-4 flex items-center space-x-2">
                    <span class="text-lg">${icon}</span>
                    <div>
                        <p class="text-xs font-bold text-white leading-none mb-1">${agent ? agent.name : 'Unknown'}</p>
                        <p class="text-[10px] text-gray-500 uppercase font-bold">${typeKey.replace('-', ' ')}</p>
                    </div>
                </td>
                <td class="px-6 py-4">
                    <span class="px-2 py-0.5 rounded text-[10px] font-black uppercase ${l.verdict === 'approve' ? 'bg-emerald-500/20 text-emerald-400' : (l.verdict === 'reject' ? 'bg-red-500/20 text-red-400' : 'bg-amber-500/20 text-amber-400')}">
                        ${actionLabel}
                    </span>
                    ${violationBadge}
                </td>
                <td class="px-6 py-4">
                    <p class="text-xs font-bold text-blue-400">${amountDisplay}</p>
                </td>
                <td class="px-6 py-4 text-right">
                    <button onclick="openLogModal('${l.id}')" class="text-blue-500 hover:text-blue-400 text-xs font-semibold">Details</button>
                </td>
            </tr>
        `;
    }).join('');
    
    window._latestLogs = logs;
}

function timeAgo(dateParam) {
    const date = typeof dateParam === 'object' ? dateParam : new Date(dateParam);
    const today = new Date();
    const seconds = Math.round((today - date) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    return `${Math.round(minutes / 60)}h ago`;
}

// --- DYNAMIC MANUAL LOG ---
function openManualLog() {
    document.getElementById("manual-log-modal").classList.remove("hidden");
    updateManualFormPersona();
}

function closeManualLog() {
    document.getElementById("manual-log-modal").classList.add("hidden");
}

function updateManualFormPersona() {
    const agentId = document.getElementById("ml-agent-select").value;
    const agent = agents.find(a => a.id === agentId);
    const typeKey = agent ? agent.agent_type : "fraud-detection";
    const meta = PERSONAS[typeKey] || PERSONAS["fraud-detection"];

    // Update banner
    const banner = document.getElementById("ml-persona-banner");
    banner.innerHTML = `<span class="text-[10px] font-black uppercase tracking-tighter text-blue-400">${meta.banner}</span>`;

    // Render Fields
    const container = document.getElementById("ml-dynamic-fields");
    container.innerHTML = meta.fields.map(f => `
        <div class="${f.id === 'confidence' ? 'col-span-1' : ''}">
            <label class="block text-xs font-bold text-gray-500 uppercase tracking-widest mb-2">${f.label}</label>
            ${f.type === 'select' ? `
                <select id="ml-field-${f.id}" onchange="updateLivePreview()" class="w-full bg-[#161b22] border border-white/10 rounded-xl px-4 py-3 text-white outline-none">
                    ${f.options.map(o => `<option value="${o}">${o}</option>`).join('')}
                </select>
            ` : `
                <input id="ml-field-${f.id}" type="${f.type}" step="${f.step||'1'}" oninput="updateLivePreview()" value="${f.value||''}" placeholder="${f.placeholder||''}" class="w-full bg-[#161b22] border border-white/10 rounded-xl px-4 py-3 text-white outline-none">
            `}
        </div>
    `).join('');

    // Update Clause Checklist
    const checklist = document.getElementById("ml-clause-checklist");
    checklist.innerHTML = meta.clauses.map(c => `
        <div class="flex items-center space-x-2 text-[10px] text-gray-500">
            <svg class="h-3 w-3 text-emerald-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
            <span>RBI Clause: ${c}</span>
        </div>
    `).join('');

    updateLivePreview();
}

function updateLivePreview() {
    const agentId = document.getElementById("ml-agent-select").value;
    const agent = agents.find(a => a.id === agentId);
    const typeKey = agent ? agent.agent_type : "fraud-detection";
    const meta = PERSONAS[typeKey] || PERSONAS["fraud-detection"];

    const previewContent = document.getElementById("ml-preview-content");
    const riskLabel = document.getElementById("ml-preview-risk");
    const riskBar = document.querySelector("#ml-risk-bar div");

    let items = [];
    if (typeKey === "fraud-detection") {
        const amount = document.getElementById("ml-field-amount").value || 0;
        const kyc = document.getElementById("ml-field-kyc_status").value;
        const pep = document.getElementById("ml-field-is_pep").value;
        
        items = [
            { l: "Amount", v: `₹${Number(amount).toLocaleString()}` },
            { l: "KYC Status", v: kyc },
            { l: "PEP Flag", v: pep === "Yes" ? "🔴 ALERT" : "🟢 Clear" }
        ];

        // Logic
        if (amount > 100000 || pep === "Yes") {
            setRiskUI("High", "text-red-500", "bg-red-500", 90);
        } else if (kyc === "Not Verified") {
            setRiskUI("Medium", "text-amber-500", "bg-amber-500", 50);
        } else {
            setRiskUI("Low", "text-emerald-500", "bg-emerald-500", 15);
        }
    } else if (typeKey === "loan-approval") {
        const score = document.getElementById("ml-field-credit_score").value || 0;
        const income = document.getElementById("ml-field-income").value || 0;
        const dti = document.getElementById("ml-field-dti").value || 0;

        const emi = Math.round((document.getElementById("ml-field-loan_amount").value || 0) * 0.02);
        
        items = [
            { l: "Credit Band", v: score > 750 ? "Excellent" : (score > 650 ? "Fair" : "Poor") },
            { l: "Est. EMI", v: `₹${emi.toLocaleString()}/mo` },
            { l: "DTI Health", v: dti < 0.4 ? "Healthy" : "Risky" }
        ];

        if (score < 600 || dti > 0.5) {
            setRiskUI("High Risk", "text-red-500", "bg-red-500", 85);
        } else if (score < 700) {
            setRiskUI("Moderate", "text-amber-500", "bg-amber-500", 45);
        } else {
            setRiskUI("Clear", "text-emerald-500", "bg-emerald-500", 10);
        }
    }

    previewContent.innerHTML = items.map(i => `
        <div class="mb-4">
            <p class="text-[10px] text-gray-500 uppercase font-black tracking-tight">${i.l}</p>
            <p class="text-lg font-bold text-white">${i.v}</p>
        </div>
    `).join('');

    function setRiskUI(text, colorClass, bgColorClass, width) {
        riskLabel.innerText = text;
        riskLabel.className = `px-2 py-0.5 ${bgColorClass}/10 ${colorClass} text-[10px] font-black rounded uppercase`;
        riskBar.className = `h-full ${bgColorClass} transition-all duration-500`;
        riskBar.style.width = `${width}%`;
    }
}

document.getElementById("manual-log-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const agentId = document.getElementById("ml-agent-select").value;
    const agent = agents.find(a => a.id === agentId);
    const typeKey = agent ? agent.agent_type : "fraud-detection";
    const meta = PERSONAS[typeKey] || PERSONAS["fraud-detection"];

    // Collect Dynamic fields
    const input = {};
    meta.fields.forEach(f => {
        input[f.id] = document.getElementById(`ml-field-${f.id}`).value;
    });

    const payload = {
        agent_id: agentId,
        input: input,
        output: { verdict: "approve" }, // Mocked for demo
        reasoning: document.getElementById("ml-reasoning").value
    };

    const res = await apiFetch("/api/manual_log", {
        method: "POST",
        body: JSON.stringify(payload)
    });

    if (res && res.verdict) {
        alert("Decision Processed via AgentBridge Gateway");
        closeManualLog();
        loadStats();
    } else {
        const err = document.getElementById("ml-error");
        err.innerText = res.detail || "Gateway Error";
        err.classList.remove("hidden");
    }
});

// --- BEHAVIOURAL DRIFT ---
async function loadDriftData() {
    // Real call: await apiFetch("/api/intelligence/drift")
    // Mock for demo
    driftData = {
        score: 34,
        alert: "⚠️ Significant behavioural drift detected in Fraud Bot — Approval rate increased by 34% this week. RBI Clause 3.1 may be at risk.",
        table: [
            { type: "Approval", last: 52, this: 86, change: 34, status: "Alert" },
            { type: "Rejection", last: 38, this: 10, change: -28, status: "Alert" },
            { type: "Verification", last: 10, this: 4, change: -6, status: "Drifting" }
        ]
    };

    renderDrift();
}

function renderDrift() {
    const alert = document.getElementById("drift-alert");
    const alertText = document.getElementById("drift-alert-text");
    if (driftData.score > 20) {
        alert.classList.remove("hidden");
        alertText.innerText = driftData.alert;
    } else {
        alert.classList.add("hidden");
    }

    document.getElementById("drift-score-label").innerText = driftData.score;
    document.getElementById("drift-bar").style.width = `${driftData.score}%`;
    document.getElementById("drift-bar").className = `h-full ${driftData.score > 20 ? 'bg-red-500' : 'bg-blue-600'} transition-all duration-1000`;

    const tbody = document.getElementById("drift-table-body");
    tbody.innerHTML = driftData.table.map(row => `
        <tr onclick="showDrilldown('${row.type}')" class="hover:bg-white/5 cursor-pointer group">
            <td class="px-4 py-3 font-bold text-white">${row.type}</td>
            <td class="px-4 py-3 text-gray-400">${row.last}%</td>
            <td class="px-4 py-3 text-gray-400">${row.this}%</td>
            <td class="px-4 py-3 ${row.change > 0 ? 'text-red-400' : 'text-emerald-400'} font-bold">
                ${row.change > 0 ? '+' : ''}${row.change}%
            </td>
            <td class="px-4 py-3">
                <span class="px-2 py-0.5 rounded-[4px] text-[9px] font-black uppercase ${row.status === 'Alert' ? 'bg-red-500/10 text-red-500' : (row.status === 'Drifting' ? 'bg-amber-500/10 text-amber-500' : 'bg-emerald-500/10 text-emerald-500')}">
                    ${row.status}
                </span>
            </td>
        </tr>
    `).join('');

    initDriftDonuts();
}

function initDriftDonuts() {
    const options = {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        cutout: '75%'
    };

    if (charts.pieLast) charts.pieLast.destroy();
    if (charts.pieThis) charts.pieThis.destroy();

    charts.pieLast = new Chart(document.getElementById('chart-pie-last'), {
        type: 'doughnut',
        data: {
            labels: ['Approve', 'Reject', 'Verify'],
            datasets: [{ data: [52, 38, 10], backgroundColor: ['#3b82f6', '#ef4444', '#f59e0b'], borderWidth: 0 }]
        },
        options
    });

    charts.pieThis = new Chart(document.getElementById('chart-pie-this'), {
        type: 'doughnut',
        data: {
            labels: ['Approve', 'Reject', 'Verify'],
            datasets: [{ data: [86, 10, 4], backgroundColor: ['#3b82f6', '#ef4444', '#f59e0b'], borderWidth: 0 }]
        },
        options
    });
}

function showDrilldown(type) {
    document.getElementById("drift-drilldown").classList.remove("hidden");
    document.getElementById("drilldown-title").innerText = `Day-by-Day ${type} Trend`;
    document.getElementById("drilldown-banner").classList.remove("hidden");
    
    // AI Explanation
    document.getElementById("drift-explanation").innerText = 
        `Fraud Bot approved ${type === 'Approval' ? '34%' : ''} more decisions this week compared to last week, primarily on Thursday and Friday. ` +
        `Average confidence dropped from 0.82 to 0.61. This may indicate model degradation or data distribution shift.`;

    if (charts.drilldown) charts.drilldown.destroy();
    charts.drilldown = new Chart(document.getElementById('chart-drilldown'), {
        type: 'line',
        data: {
            labels: Array.from({length: 14}, (_, i) => `Mar ${22+i}`),
            datasets: [
                { label: 'Action %', data: [50, 52, 48, 51, 55, 60, 68, 75, 80, 84, 86, 85, 86, 86], borderColor: '#3b82f6', tension: 0.4 },
                { label: 'Confidence', data: [85, 84, 82, 80, 78, 75, 70, 68, 65, 62, 61, 60, 61, 61], borderColor: '#888', borderDash: [5, 5], tension: 0.4 }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { y: { display: false }, x: { grid: { display: false }, ticks: { color: '#444', font: { size: 9 } } } }
        }
    });
}

function closeDrilldown() {
    document.getElementById("drift-drilldown").classList.add("hidden");
    document.getElementById("drilldown-banner").classList.add("hidden");
}

// --- TAB MGMT ---
function showTab(tab) {
    currentTab = tab;
    document.querySelectorAll('[id^="section-"]').forEach(s => s.classList.add("hidden"));
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove("active"));
    
    document.getElementById(`section-${tab}`).classList.remove("hidden");
    document.getElementById(`btn-${tab}`).classList.add("active");
    
    const titles = {
        'dashboard': 'Control Center',
        'agents': 'AI Agent Registry',
        'reports': 'Regulatory Compliance',
        'incidents': 'Security Incidents',
        'intelligence': 'Compliance Brain',
        'settings': 'System Configuration'
    };
    document.getElementById("tab-title").innerText = titles[tab] || 'AgentBridge';

    if (tab === "intelligence") {
        loadDriftData();
        initVolumeChart();
    }
}

function initVolumeChart() {
    if (charts.volume) return;
    charts.volume = new Chart(document.getElementById('chart-volume'), {
        type: 'line',
        data: {
            labels: Array.from({length: 10}, (_, i) => `Apr ${i+1}`),
            datasets: [{
                label: 'Decisions',
                data: [120, 190, 300, 500, 200, 300, 450, 400, 500, 600],
                borderColor: '#3b82f6',
                fill: true,
                backgroundColor: 'rgba(59, 130, 246, 0.05)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { y: { display: false }, x: { grid: { display: false }, ticks: { color: '#444', font: { size: 9 } } } }
        }
    });
}

// --- OTHER UTILS ---
function openLogModal(id) {
    const log = window._latestLogs.find(l => l.id === id);
    if (!log) return;
    document.getElementById("modal-log-id").innerText = `#${log.decision_id}`;
    
    const logJson = typeof log === 'string' ? JSON.parse(log) : log;
    document.getElementById("log-json").innerText = JSON.stringify(logJson, null, 4);
    document.getElementById("log-modal").classList.remove("hidden");
}

function closeLogModal() {
    document.getElementById("log-modal").classList.add("hidden");
}

function logout() {
    localStorage.clear();
    window.location.href = "login.html";
}

function closeOnboarding() {
    localStorage.setItem("onboarding_done", "true");
    document.getElementById("onboarding-modal").classList.add("hidden");
}
