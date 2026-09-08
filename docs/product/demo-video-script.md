# Enterprise AI Analyst — Demo Video Storyboard & Recording Script 🎬

This document provides a precise, second-by-second storyboard for recording a **3–5 minute high-impact portfolio demo video** for hiring managers, technical leads, and recruiters.

---

## 🎯 Video Objective
Demonstrate that **Enterprise AI Analyst** is not a shallow ChatGPT wrapper, but a **full-stack, verifiable enterprise intelligence platform** combining Hybrid RAG, AST Text-to-SQL, Knowledge Graphs, Agent Orchestration, SRE Reliability, and FinOps cost governance.

* **Target Length**: 4 minutes 30 seconds.
* **Recording Resolution**: 1080p (1920x1080) or 4K.
* **Theme**: Sleek Dark Mode (`#09090b`).
* **Browser URL**: `http://localhost:3000`.

---

## ⏱️ Timeline & Scene Breakdown

```text
00:00 — 00:25 (25s) : 1. The Hook & Platform Introduction
00:25 — 00:50 (25s) : 2. Executive Overview Dashboard
00:50 — 01:40 (50s) : 3. The Star: Complex AI Analyst Inquiry & Real-Time SSE
01:40 — 02:15 (35s) : 4. Grounded Evidence Inspection & Provenance Citations [S1], [D1]
02:15 — 02:50 (35s) : 5. Multi-Modal Verification: AST Text-to-SQL & Graph Traversal
02:50 — 03:25 (35s) : 6. Agent Runtime, Governance Quorum & Checkpoints
03:25 — 03:55 (30s) : 7. Operations, SRE & Chaos Resilience
03:55 — 04:20 (25s) : 8. FinOps Cost Attribution & Real-Time Ledger
04:20 — 04:45 (25s) : 9. Architecture Showcase, GitHub & Outro
```

---

## 📝 Detailed Script & Screen Actions

### Scene 1: The Hook & Introduction (00:00 — 00:25)
* **Screen**: Start on the **Showcase & Architecture Tour** page (`/showcase`).
* **Visual Action**: Smooth scroll down past the 4 architectural layers, highlighting the badges.
* **Voiceover (English)**:
  > *"Most enterprise AI projects fail in production because they are built as shallow API wrappers that hallucinate numbers, breach tenant boundaries, and have zero cost controls. This is Enterprise AI Analyst — an end-to-end, multi-modal intelligence platform that connects structured financial ledgers, unstructured documents, and knowledge graphs into a single, verifiable analytical engine with zero-hallucination guarantees."*
* **Voiceover (Arabic Alternative)**:
  > *"أغلب مشاريع الذكاء الاصطناعي تفشل في بيئات العمل الحقيقية لأنها مجرد واجهات بسيطة فوق الـ LLMs، تختلق الأرقام وتفتقر للأدلة. هذا المشروع هو Enterprise AI Analyst: منصة متكاملة للذكاء الاصطناعي تربط قواعد البيانات المالية، الوثائق المفهرسة، ومخططات المعرفة، مع ضمانات صارمة لعدم الهلوسة وإسناد الأدلة الحقيقية."*

---

### Scene 2: Executive Overview Dashboard (00:25 — 00:50)
* **Screen**: Navigate to **Overview Dashboard** (`/`).
* **Visual Action**:
  - Hover over the 4 KPI stat cards (FinOps Spend, Indexed Records, AI Inquiries, Platform SLO).
  - Hover over the Recharts AreaChart showing actual spend vs allocated quota.
  - Press `⌘K` to open the Command Palette, search "Analyst", and press Enter.
* **Voiceover**:
  > *"Here on the Overview Dashboard, everything you see is bound to real production metrics. We monitor real-time FinOps spend against tenant quotas, live system availability at 99.95%, and recent multi-source analyses. With our global command palette, users can instantly jump across workspaces using keyboard shortcuts."*

---

### Scene 3: The Star: Complex Inquiry & Real-Time SSE (00:50 — 01:40)
* **Screen**: AI Analyst Research Workspace (`/analyst`).
* **Visual Action**:
  - Paste the canonical killer demo question into the composer:
    ```text
    Why did Q3 operating margin contract in North America despite enterprise ARR growth, verify with ledger records, and outline customer churn risks?
    ```
  - Select mode `AUTO`, response style `STANDARD`, and ensure `Stream (SSE)` is checked.
  - Click **Ask**.
  - Show the progressive thinking timeline as stages illuminate (`UNDERSTANDING` → `SEMANTIC` → `EXECUTION` → `EVIDENCE`).
  - Watch the markdown answer stream smoothly with the blinking cursor.
* **Voiceover**:
  > *"Now for the core capability: let's ask a multi-layered financial question requiring both structured SQL ledger data and unstructured document filings. Notice our SSE stream: the system progressively updates the timeline from query understanding to semantic resolution and parallel execution. The answer streams in real time, completely structured with financial tables, bullet points, and specific claim citations."*

---

### Scene 4: Grounded Evidence & Provenance Citations (01:40 — 02:15)
* **Screen**: AI Analyst Response Area.
* **Visual Action**:
  - Point to the **Groundedness Meter** bar showing `94.7%` in green.
  - Click citation pill **`[S1]`**: the Evidence drawer slides out revealing the raw SQL query on `enterprise_ledgers` and exact row value ($142.8M).
  - Click citation pill **`[D1]`**: show the extracted paragraph from the SEC 10-Q filing.
  - Click the **Copy** and **Export** buttons to show interactive craft touches.
* **Voiceover**:
  > *"Unlike standard chat interfaces, every single assertion here is mathematically grounded. We see a Groundedness score of 94.7%. When I click citation S1, the evidence panel immediately displays the exact read-only SQL query executed on Postgres and the resulting revenue row. Clicking D1 exposes the exact vector-retrieved chunk from our Q3 financial report. Zero blind trust — full auditability."*

---

### Scene 5: Multi-Modal Verification: AST SQL & Graph (02:15 — 02:50)
* **Screen**: Expand the **Execution Details / Parallel Branches** panel.
* **Visual Action**:
  - Show the 3 parallel branches:
    1. SQL branch: Show that the query was parsed with an Abstract Syntax Tree (AST), ensuring read-only permissions and row limits.
    2. RAG branch: Hybrid RRF fusion score.
    3. Knowledge Graph branch: Multi-hop entity path linking North American tier accounts.
* **Voiceover**:
  > *"Under the hood, the platform decomposed this single question into 3 parallel execution branches. Our AST Text-to-SQL engine validated that the query contains no mutating DDL/DML, automatically injected tenant isolation filters, and enforced row limits. Simultaneously, the hybrid RAG engine ran dense and sparse BM25 retrieval fused with Reciprocal Rank Fusion, while the Knowledge Graph traversed entity dependencies."*

---

### Scene 6: Agent Runtime & Governance Quorum (02:50 — 03:25)
* **Screen**: Navigate to **Executions & Approvals** (`/executions` and `/approvals`).
* **Visual Action**:
  - Show the 10-state Agent Finite State Machine timeline.
  - Show how sensitive actions trigger a **Human-in-the-loop Approval** requirement.
  - Show the Risk Score badge and Approve/Reject controls.
* **Voiceover**:
  > *"When an agent plans actions that touch sensitive tables or exceed operational risk thresholds, it enters our 10-state Finite State Machine checkpoint. The session pauses, state is persisted in Postgres, and a Human Approval Quorum is triggered. Only authorized administrators can approve or reject the action, preventing TOCTOU race conditions."*

---

### Scene 7: SRE, Operations & Chaos Resilience (03:25 — 03:55)
* **Screen**: Navigate to **Operations** (`/operations`) and **Reliability** (`/operations/reliability`).
* **Visual Action**:
  - Show the SLO compliance meter (99.95%).
  - Show Error Budget burn rate bars (1h, 6h, 24h).
  - Highlight the Chaos Scenarios table showing database partition recovery.
* **Voiceover**:
  > *"In the Operations Hub, we track site reliability engineering metrics including multi-window error budget burn rates and automated incident lifecycle states. Through our chaos reliability suite, we run automated fault injection tests simulating database disconnects and Redis cache partitions, proving rapid automated recovery."*

---

### Scene 8: FinOps Cost Governance (03:55 — 04:20)
* **Screen**: Navigate to **FinOps Hub** (`/finops`).
* **Visual Action**:
  - Show the live spend gauge, model cost breakdown (OpenAI vs Anthropic vs Local), and quota cap status.
  - Point out that our earlier demo query automatically incremented the cost ledger by $0.0034.
* **Voiceover**:
  > *"Enterprise AI requires strict financial discipline. Our FinOps engine prices every single prompt and completion token in real time against multi-provider rate cards. Organizations have enforced daily and monthly budgets that automatically soft-alert at 75% and hard-block before cost overruns can happen."*

---

### Scene 9: Architecture Showcase, GitHub & Outro (04:20 — 04:45)
* **Screen**: Return to **Showcase** (`/showcase`) or display root **GitHub README.md**.
* **Visual Action**:
  - Scroll past the comprehensive README badges, architecture diagram, and test matrix.
  - End on the full-screen view of the application with the language toggle clicked to Turkish and back to English.
* **Voiceover**:
  > *"With 288 automated backend tests, 25 frontend tests, and 36 certified production routes across Next.js 16, FastAPI, Postgres, and Qdrant, Enterprise AI Analyst represents a complete, production-grade AI platform. Check out the GitHub repository below for full documentation, architectural blueprints, and reproducible quickstart commands. Thank you for watching!"*

---

## 💡 Top 5 Tips for Video Recording
1. **Clear Browser Cache / Open Incognito**: Ensure clean dark styling with no browser extensions cluttering the topbar.
2. **Deterministic Seed**: Always run `python scripts/demo/setup_demo.py` prior to recording to ensure fresh, clean statistics.
3. **Smooth Cursor Movement**: Avoid rapid mouse jerks; glide smoothly between cards, buttons, and citation pills.
4. **Use Keyboard Shortcut**: Press `⌘K` naturally during the dashboard scene to highlight the platform's professional feel.
5. **Enthusiastic, Steady Pacing**: Maintain a confident, senior engineering tone throughout.
