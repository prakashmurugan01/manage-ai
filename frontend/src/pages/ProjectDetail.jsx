import {
  Activity,
  BarChart3,
  Bot,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  Cloud,
  Code2,
  Database,
  Download,
  FileArchive,
  FileText,
  Folder,
  GitBranch,
  Globe2,
  HardDrive,
  History,
  Layers,
  Lightbulb,
  MessageSquare,
  MessageSquareWarning,
  Package,
  Plus,
  RefreshCw,
  Rocket,
  Settings,
  ShieldCheck,
  UploadCloud,
  UsersRound,
  WalletCards,
  Wrench
} from "lucide-react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { listFrom } from "../api/client.js";
import { aiApi, deploymentsApi, projectsApi, tasksApi } from "../api/services.js";
import DeploymentToggle from "../components/projects/DeploymentToggle.jsx";
import ProjectConnectionPanel from "../components/projects/ProjectConnectionPanel.jsx";
import ProjectFlowPanel from "../components/projects/ProjectFlowPanel.jsx";
import KanbanBoard from "../components/tasks/KanbanBoard.jsx";
import Badge from "../components/ui/Badge.jsx";
import Button from "../components/ui/Button.jsx";
import Modal from "../components/ui/Modal.jsx";
import Page from "../components/ui/Page.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { dateShort, pct } from "../utils/format.js";
import { canManage } from "../utils/rbac.js";

const DETAIL_TABS = [
  ["overview", "Overview", Activity],
  ["tasks", "Tasks", ClipboardList],
  ["developers", "Developers", UsersRound],
  ["messages", "Messages", MessageSquare],
  ["files", "Files", Folder],
  ["backups", "Backups", FileArchive],
  ["invoices", "Invoices", WalletCards],
  ["hosting", "Hosting", Globe2],
  ["deployments", "Deployments", Rocket],
  ["analytics", "Analytics", BarChart3],
  ["timeline", "Timeline", History],
  ["ai", "AI Assistant", Bot],
  ["settings", "Settings", Settings]
];

const STACK_GROUPS = [
  { label: "Frontend", icon: Code2, keywords: ["react", "next", "vue", "angular", "vite", "tailwind", "html", "css"] },
  { label: "Backend", icon: Package, keywords: ["django", "flask", "fastapi", "node", "express", "laravel", "spring"] },
  { label: "Database", icon: Database, keywords: ["mysql", "postgres", "postgresql", "mongo", "sqlite", "redis", "mariadb"] },
  { label: "Cloud", icon: Cloud, keywords: ["aws", "azure", "cloudflare", "vercel", "netlify", "digitalocean", "render", "railway"] }
];

const FILE_TREE = [
  { name: "Source Code", icon: Folder, children: ["Frontend", "Backend", "Database"] },
  { name: "Documents", icon: Folder, children: ["Proposal.pdf", "Invoice.pdf", "Requirement.docx"] },
  { name: "Deployments", icon: Folder, children: ["Build_v1.zip", "Build_v2.zip"] },
  { name: "Backups", icon: Folder, children: ["Backup_01.zip", "Backup_02.zip"] }
];

const BACKUP_ROWS = [
  { name: "Database Backup", detail: "Database schema and project records", icon: Database },
  { name: "Project Files Backup", detail: "Uploaded source, documents, and assets", icon: Folder },
  { name: "Full Project Backup", detail: "Files, records, invoices, and deployment metadata", icon: HardDrive }
];

const ROLE_ROWS = [
  "Team Lead",
  "Frontend Developer",
  "Backend Developer",
  "UI Designer",
  "Tester",
  "DevOps Engineer"
];

export default function ProjectDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [project, setProject] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [deployment, setDeployment] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [taskOpen, setTaskOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");
  const [taskForm, setTaskForm] = useState({
    title: "",
    description: "",
    priority: "MEDIUM",
    status: "BACKLOG",
    workflow_day: 1,
    assignee: "",
    due_date: "",
    project: id
  });

  const manager = canManage(user);
  const finance = projectFinance(project);
  const summary = taskSummary(tasks);

  useEffect(() => {
    projectsApi.get(id).then(({ data }) => setProject(data));
    projectsApi.kanban(id).then((response) => setTasks(listFrom(response)));
    deploymentsApi.list({ project: id }).then((response) => setDeployment(listFrom(response)[0]));
    aiApi.list({ project: id }).then((response) => setSuggestions(listFrom(response)));
  }, [id]);

  async function createTask(event) {
    event.preventDefault();
    const payload = { ...taskForm, project: id, assignee: taskForm.assignee || null };
    if (!payload.due_date) delete payload.due_date;
    const { data } = await tasksApi.create(payload);
    setTasks((items) => [data, ...items]);
    setTaskOpen(false);
    setActiveTab("tasks");
  }

  async function generateSuggestions() {
    const { data } = await aiApi.generate({ project: Number(id), context: project?.description, limit: 4 });
    setSuggestions(data);
  }

  async function approveSuggestion(suggestion) {
    const { data } = await aiApi.approve(suggestion.id, { status: "BACKLOG" });
    setTasks((items) => [data, ...items]);
    setSuggestions((items) => items.map((item) => (item.id === suggestion.id ? { ...item, status: "APPROVED" } : item)));
  }

  async function reviewProject(approvalStatus, approvalNote) {
    const { data } = await projectsApi.review(id, { approval_status: approvalStatus, approval_note: approvalNote });
    setProject(data);
  }

  return (
    <Page
      title={project?.name || "Project"}
      subtitle={project?.description || "Enterprise project command center for delivery, finance, hosting, files, and AI operations."}
      actions={
        <>
          {deployment && manager && <DeploymentToggle deployment={deployment} onChange={setDeployment} />}
          {manager && (
            <Button onClick={() => setTaskOpen(true)}>
              <Plus size={16} />
              Task
            </Button>
          )}
        </>
      }
    >
      <ProjectCommandBar project={project} finance={finance} summary={summary} deployment={deployment} />

      <ApprovalPanel project={project} canEdit={manager} onReview={reviewProject} />

      <ProjectTabs activeTab={activeTab} onChange={setActiveTab} />

      <div className="mt-6">
        {activeTab === "overview" && (
          <OverviewTab
            project={project}
            finance={finance}
            summary={summary}
            deployment={deployment}
            canEdit={manager}
            onProjectChange={setProject}
          />
        )}

        {activeTab === "tasks" && (
          <TasksTab
            tasks={tasks}
            project={project}
            summary={summary}
            canEdit={manager}
            onCreateTask={() => setTaskOpen(true)}
            onTasksChange={setTasks}
          />
        )}

        {activeTab === "developers" && <DevelopersTab project={project} tasks={tasks} />}

        {activeTab === "messages" && <MessagesTab project={project} suggestions={suggestions} />}

        {activeTab === "files" && <FilesTab project={project} />}

        {activeTab === "backups" && <BackupsTab project={project} />}

        {activeTab === "invoices" && <InvoicesTab project={project} finance={finance} />}

        {activeTab === "hosting" && <HostingTab project={project} deployment={deployment} />}

        {activeTab === "deployments" && (
          <DeploymentsTab
            project={project}
            user={user}
            deployment={deployment}
            onProjectChange={setProject}
            onDeploymentChange={setDeployment}
          />
        )}

        {activeTab === "analytics" && <AnalyticsTab project={project} tasks={tasks} finance={finance} summary={summary} />}

        {activeTab === "timeline" && <TimelineTab project={project} tasks={tasks} deployment={deployment} />}

        {activeTab === "ai" && (
          <AITab
            project={project}
            tasks={tasks}
            suggestions={suggestions}
            canEdit={manager}
            onGenerate={generateSuggestions}
            onApprove={approveSuggestion}
          />
        )}

        {activeTab === "settings" && (
          <SettingsTab project={project} canEdit={manager} onReview={reviewProject} />
        )}
      </div>

      <TaskModal
        open={taskOpen}
        project={project}
        taskForm={taskForm}
        setTaskForm={setTaskForm}
        onClose={() => setTaskOpen(false)}
        onSubmit={createTask}
      />
    </Page>
  );
}

function ProjectCommandBar({ project, finance, summary, deployment }) {
  const client = project?.client_detail;
  return (
    <div className="mb-6 grid gap-4 xl:grid-cols-6">
      <MetricTile icon={ShieldCheck} label="Status" value={project?.status || "Loading"} badge={project?.approval_status || "DRAFT"} />
      <MetricTile icon={Activity} label="Priority" value={project?.priority || "Not set"} badge={project?.system_status || "HEALTHY"} />
      <MetricTile icon={BarChart3} label="Progress" value={pct(project?.progress)} detail={`${summary.done} done / ${summary.total} tasks`} />
      <MetricTile icon={Rocket} label="Deployment" value={deployment?.is_enabled ? "ON" : "OFF"} detail={project?.latest_deployment_status || "Not deployed"} />
      <MetricTile icon={CalendarDays} label="Deadline" value={dateShort(project?.due_date)} detail={client ? displayName(client) : "No client"} />
      <MetricTile icon={WalletCards} label="Revenue" value={money(finance.total)} detail={`${money(finance.pending)} pending`} />
    </div>
  );
}

function ApprovalPanel({ project, canEdit, onReview }) {
  return (
    <div className="mb-6 panel p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="label">Project Approval</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge value={project?.approval_status || "DRAFT"} />
            {project?.approval_note && <span className="text-sm text-slate-400">{project.approval_note}</span>}
            {project?.approved_at && <span className="text-sm text-slate-500">Approved {dateShort(project.approved_at)}</span>}
          </div>
        </div>
        {canEdit && (
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => onReview("IN_REVIEW", "Submitted for review")}>
              <ClipboardList size={16} />
              Review
            </Button>
            <Button onClick={() => onReview("APPROVED", "Project approved")}>
              <CheckCircle2 size={16} />
              Approve
            </Button>
            <Button variant="ghost" onClick={() => onReview("CORRECTION_REQUESTED", "Correction requested")}>
              <MessageSquareWarning size={16} />
              Request Correction
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

function ProjectTabs({ activeTab, onChange }) {
  return (
    <div className="overflow-x-auto pb-1 scrollbar-thin">
      <div className="flex min-w-max gap-2 rounded-lg border border-white/10 bg-white/[0.03] p-1">
        {DETAIL_TABS.map(([id, label, Icon]) => (
          <button
            key={id}
            type="button"
            onClick={() => onChange(id)}
            className={`inline-flex h-10 items-center gap-2 rounded-md px-3 text-sm font-semibold transition ${
              activeTab === id
                ? "bg-[color:var(--accent)] text-white shadow-sm"
                : "text-slate-400 hover:bg-white/10 hover:text-white"
            }`}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

function OverviewTab({ project, finance, summary, deployment, canEdit, onProjectChange }) {
  return (
    <>
      <ProjectOverviewSection project={project} finance={finance} summary={summary} />
      <ProjectFlowPanel project={project} canEdit={canEdit} onProjectChange={onProjectChange} />
      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <ProjectBlueprint project={project} />
        <AssignedTeam project={project} />
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_0.9fr]">
        <TechnologyStack project={project} />
        <HostingSnapshot project={project} deployment={deployment} />
      </div>
    </>
  );
}

function TasksTab({ tasks, project, summary, canEdit, onCreateTask, onTasksChange }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-4">
        <MiniStat label="Total Tasks" value={summary.total} icon={ClipboardList} />
        <MiniStat label="Open" value={summary.open} icon={Activity} />
        <MiniStat label="Blocked" value={summary.blocked} icon={MessageSquareWarning} />
        <MiniStat label="Workflow Days" value={project?.workflow_days || 7} icon={CalendarDays} />
      </div>
      <div className="panel p-4">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white">Delivery Kanban</h2>
            <p className="mt-1 text-sm text-slate-400">Backlog, active work, review, completed items, and blockers.</p>
          </div>
          {canEdit && (
            <Button variant="secondary" onClick={onCreateTask}>
              <Plus size={16} />
              Add Task
            </Button>
          )}
        </div>
        <KanbanBoard tasks={tasks} workflowDays={project?.workflow_days || 7} onTasksChange={onTasksChange} />
      </div>
    </div>
  );
}

function DevelopersTab({ project, tasks }) {
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
      <AssignedTeam project={project} />
      <div className="panel p-4">
        <PanelHeading icon={UsersRound} title="Developer Assignment Matrix" subtitle="Role coverage, task load, and project responsibility." />
        <div className="mt-4 grid gap-3">
          {ROLE_ROWS.map((role, index) => {
            const developer = (project?.developers_detail || [])[index];
            return (
              <div key={role} className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.035] px-3 py-2">
                <div>
                  <p className="text-sm font-semibold text-white">{role}</p>
                  <p className="text-xs text-slate-500">{developer ? developer.role_title || developer.department || "Assigned" : "Not assigned"}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium text-slate-200">{developer ? displayName(developer) : "Open"}</p>
                  <p className="text-xs text-slate-500">{developerTaskCount(tasks, developer?.id)} active tasks</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function MessagesTab({ project, suggestions }) {
  const [channel, setChannel] = useState("client");
  const channels = [
    ["client", "Client Messages"],
    ["admin", "Admin Messages"],
    ["developer", "Developer Messages"],
    ["ai", "AI Suggestions"]
  ];
  const messages = messageRows(project, suggestions, channel);

  return (
    <div className="panel p-4">
      <PanelHeading icon={MessageSquare} title="Client Communication Center" subtitle="Client, admin, developer, and AI project conversation lanes." />
      <div className="mt-4 flex flex-wrap gap-2">
        {channels.map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setChannel(id)}
            className={`rounded-md px-3 py-2 text-sm font-semibold transition ${
              channel === id ? "bg-[color:var(--accent)] text-white" : "bg-white/[0.04] text-slate-400 hover:bg-white/10"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="mt-4 grid gap-3">
        {messages.map((message) => (
          <div key={`${message.author}-${message.text}`} className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-white">{message.author}</p>
              <span className="text-xs text-slate-500">{message.time}</span>
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-300">{message.text}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_auto]">
        <input className="field" placeholder="@Prakash Please update the dashboard UI." />
        <Button variant="secondary" disabled>
          <UploadCloud size={16} />
          Attach
        </Button>
      </div>
    </div>
  );
}

function FilesTab({ project }) {
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_0.85fr]">
      <ProjectFileManager project={project} />
      <div className="panel p-4">
        <PanelHeading icon={UploadCloud} title="Upload Controls" subtitle="Server upload gate, document intake, and review routing." />
        <div className="mt-4 rounded-lg border border-emerald-300/20 bg-emerald-300/10 p-3 text-sm text-emerald-100">
          Admin upload gate active
        </div>
        <div className="mt-4 grid gap-3">
          <input className="field" placeholder="Title" />
          <select className="field" defaultValue="Internal">
            <option>Internal</option>
            <option>Client Visible</option>
            <option>Developer Only</option>
          </select>
          <div className="rounded-lg border border-white/10 bg-white/[0.035] p-3 text-sm text-slate-400">
            Use Developer Submission in the Deployments tab for live server storage upload.
          </div>
        </div>
      </div>
    </div>
  );
}

function BackupsTab({ project }) {
  return (
    <div className="panel p-4">
      <PanelHeading icon={FileArchive} title="Backup Center" subtitle="Database, file, and full-project backup operations." />
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {BACKUP_ROWS.map((item) => (
          <div key={item.name} className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
            <item.icon size={20} className="text-cyan-300" />
            <h3 className="mt-3 text-sm font-semibold text-white">{item.name}</h3>
            <p className="mt-2 text-xs leading-5 text-slate-400">{item.detail}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button variant="secondary" disabled>Create</Button>
              <Button variant="ghost" disabled>Restore</Button>
              <Button variant="ghost" disabled>Download</Button>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 overflow-hidden rounded-lg border border-white/10">
        <BackupRow name={`${project?.slug || "project"}-full-backup.zip`} date={project?.updated_at} size="Pending" user={project?.owner_detail} />
        <BackupRow name={`${project?.slug || "project"}-database.sql`} date={project?.created_at} size="Pending" user={project?.created_by} />
      </div>
    </div>
  );
}

function InvoicesTab({ project, finance }) {
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
      <FinancialManagement finance={finance} />
      <div className="panel p-4">
        <PanelHeading icon={FileText} title="Invoice Management" subtitle="Quotation, receipt, tax invoice, and project payment records." />
        <div className="mt-4 grid gap-3">
          {[
            ["Quotation PDF", "Scope and pricing proposal"],
            ["Invoice PDF", "Client payment invoice"],
            ["Payment Receipt PDF", "Paid amount confirmation"],
            ["Tax Invoice", "GST and tax-compliant invoice"]
          ].map(([title, detail]) => (
            <div key={title} className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.035] px-3 py-2">
              <div>
                <p className="text-sm font-semibold text-white">{title}</p>
                <p className="text-xs text-slate-500">{detail}</p>
              </div>
              <Button variant="secondary" disabled>
                <Download size={15} />
                Generate
              </Button>
            </div>
          ))}
        </div>
        <div className="mt-4 rounded-lg border border-white/10 bg-white/[0.035] p-3">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Payment Status</p>
          <div className="mt-2 flex items-center gap-2">
            <Badge value={finance.status} />
            <span className="text-sm text-slate-400">{project?.client_detail?.email || "Client email not set"}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function HostingTab({ project, deployment }) {
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
      <HostingCenter project={project} deployment={deployment} />
      <div className="panel p-4">
        <PanelHeading icon={ShieldCheck} title="Domain, SSL, and Uptime" subtitle="Operational health for hosted project assets." />
        <div className="mt-4 grid gap-3">
          <InfoRow label="Domain" value={project?.domain_name || "Not configured"} />
          <InfoRow label="SSL" value={sslLabel(project)} />
          <InfoRow label="System Status" value={project?.system_status || "HEALTHY"} badge />
          <InfoRow label="Uptime" value={`${Number(project?.uptime_percentage || 100).toFixed(2)}%`} />
          <InfoRow label="Hosting Renewal" value={dateShort(project?.renewal_date || project?.hosting_expiry_date)} />
          <InfoRow label="Domain Expiry" value={dateShort(project?.domain_expiry_date)} />
        </div>
      </div>
    </div>
  );
}

function DeploymentsTab({ project, user, deployment, onProjectChange, onDeploymentChange }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-4">
        <MiniStat label="Provider" value={project?.hosting_provider || "Not set"} icon={Cloud} />
        <MiniStat label="Deploy Status" value={project?.latest_deployment_status || "Not deployed"} icon={Rocket} />
        <MiniStat label="Branch" value={project?.selected_branch || project?.github_default_branch || "main"} icon={GitBranch} />
        <MiniStat label="Last Sync" value={dateShort(project?.last_synced_at)} icon={RefreshCw} />
      </div>
      {project && (
        <ProjectConnectionPanel
          project={project}
          user={user}
          deployment={deployment}
          onProjectChange={onProjectChange}
          onDeploymentChange={onDeploymentChange}
        />
      )}
    </div>
  );
}

function AnalyticsTab({ project, tasks, finance, summary }) {
  const risk = riskLevel(project, tasks);
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
      <div className="panel p-4">
        <PanelHeading icon={BarChart3} title="Project Analytics Dashboard" subtitle="Revenue, productivity, task movement, and deployment health." />
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <MiniStat label="Total Revenue" value={money(finance.total)} icon={WalletCards} />
          <MiniStat label="Pending Revenue" value={money(finance.pending)} icon={WalletCards} />
          <MiniStat label="Team Productivity" value={`${Math.max(0, 100 - summary.blocked * 12)}%`} icon={UsersRound} />
          <MiniStat label="Tasks Completed" value={summary.done} icon={CheckCircle2} />
          <MiniStat label="Tasks Pending" value={summary.open} icon={ClipboardList} />
          <MiniStat label="Risk Level" value={risk} icon={ShieldCheck} />
        </div>
        <div className="mt-5 grid gap-3">
          <ProgressBar label="Delivery Progress" value={Number(project?.progress || 0)} />
          <ProgressBar label="Health Score" value={Number(project?.health_score || 100)} />
          <ProgressBar label="Uptime" value={Number(project?.uptime_percentage || 100)} />
        </div>
      </div>
      <ActivityTimeline project={project} tasks={tasks} />
    </div>
  );
}

function TimelineTab({ project, tasks, deployment }) {
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_0.85fr]">
      <ActivityTimeline project={project} tasks={tasks} deployment={deployment} />
      <div className="panel p-4">
        <PanelHeading icon={History} title="Audit Snapshot" subtitle="Important project lifecycle timestamps." />
        <div className="mt-4 grid gap-3">
          <InfoRow label="Created" value={dateShort(project?.created_at)} />
          <InfoRow label="Updated" value={dateShort(project?.updated_at)} />
          <InfoRow label="Approved" value={dateShort(project?.approved_at)} />
          <InfoRow label="Flow Generated" value={dateShort(project?.flow_generated_at)} />
          <InfoRow label="Latest Deployment" value={dateShort(project?.latest_deployment_at)} />
          <InfoRow label="Latest Commit" value={dateShort(project?.last_commit_at)} />
        </div>
      </div>
    </div>
  );
}

function AITab({ project, tasks, suggestions, canEdit, onGenerate, onApprove }) {
  const analysis = aiAnalysis(project, tasks);
  return (
    <div className="grid gap-4 xl:grid-cols-[0.9fr_1fr]">
      <div className="panel p-4">
        <PanelHeading icon={Bot} title="Project AI Assistant" subtitle="Completion estimate, risks, missing modules, and generated delivery help." />
        <div className="mt-4 grid gap-3">
          <InfoRow label="Estimated Completion" value={`${analysis.days} days`} />
          <InfoRow label="Risk Level" value={analysis.risk} badge />
          <InfoRow label="Suggested Developers" value={analysis.developers} />
          <InfoRow label="Missing Modules" value={analysis.missingModules} />
        </div>
        <div className="mt-4 grid gap-2">
          {["Generate tasks", "Generate documentation", "Generate deployment steps", "Generate bug report", "Generate release notes"].map((action) => (
            <Button key={action} variant="secondary" disabled>
              <SparkIcon />
              {action}
            </Button>
          ))}
        </div>
      </div>
      {canEdit && (
        <div className="panel p-4">
          <div className="flex items-center justify-between gap-3">
            <PanelHeading icon={BrainIcon} title="AI Task Suggestions" subtitle="Review AI generated scope items and convert useful ones into tasks." />
            <Button variant="secondary" onClick={onGenerate}>
              <Bot size={16} />
              Generate
            </Button>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {suggestions.map((suggestion) => (
              <div key={suggestion.id} className="surface-soft rounded-lg p-3">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-medium text-white">{suggestion.title}</h3>
                  <Badge value={suggestion.status} />
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-400">{suggestion.rationale}</p>
                {suggestion.status === "DRAFT" && (
                  <Button className="mt-3" variant="secondary" onClick={() => onApprove(suggestion)}>
                    Approve
                  </Button>
                )}
              </div>
            ))}
            {!suggestions.length && <EmptyPanel text="No AI suggestions generated yet." />}
          </div>
        </div>
      )}
    </div>
  );
}

function SettingsTab({ project, canEdit, onReview }) {
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
      <div className="panel p-4">
        <PanelHeading icon={Settings} title="Advanced Admin Controls" subtitle="Approval, lifecycle, cloning, transfer, archive, and correction controls." />
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          <Button disabled={!canEdit} onClick={() => onReview("APPROVED", "Project approved")}>
            <CheckCircle2 size={16} />
            Approve Project
          </Button>
          <Button disabled={!canEdit} variant="ghost" onClick={() => onReview("CORRECTION_REQUESTED", "Correction requested")}>
            <MessageSquareWarning size={16} />
            Request Correction
          </Button>
          <Button disabled variant="secondary">Reject Project</Button>
          <Button disabled variant="secondary">Suspend Project</Button>
          <Button disabled variant="secondary">Archive Project</Button>
          <Button disabled variant="secondary">Clone Project</Button>
          <Button disabled variant="secondary">Transfer Project</Button>
          <Button disabled variant="danger">Delete Project</Button>
        </div>
      </div>
      <div className="panel p-4">
        <PanelHeading icon={Layers} title="Project Settings Snapshot" subtitle="Core IDs, status fields, tags, and lifecycle metadata." />
        <div className="mt-4 grid gap-3">
          <InfoRow label="Project ID" value={projectCode(project)} />
          <InfoRow label="Slug" value={project?.slug || "Not set"} />
          <InfoRow label="Connection" value={project?.connection_type || "NONE"} badge />
          <InfoRow label="Connection Status" value={project?.connection_status || "DISCONNECTED"} badge />
          <InfoRow label="Tags" value={safeList(project?.tags).join(", ") || "None"} />
        </div>
      </div>
    </div>
  );
}

function ProjectOverviewSection({ project, finance, summary }) {
  const client = project?.client_detail || {};
  const meta = metadata(project);
  return (
    <div className="mb-6 panel p-4">
      <PanelHeading icon={Layers} title="Project Overview" subtitle="Commercial, client, delivery, and lifecycle information." />
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <InfoCell label="Project ID" value={projectCode(project)} />
        <InfoCell label="Project Name" value={project?.name || "Loading"} />
        <InfoCell label="Project Type" value={project?.project_type || meta.project_type || "General"} />
        <InfoCell label="Project Category" value={meta.category || safeList(project?.tags)[0] || "Software"} />
        <InfoCell label="Client Name" value={displayName(client) || "Not assigned"} />
        <InfoCell label="Client Company" value={client.company || meta.client_company || "Not set"} />
        <InfoCell label="Client Email" value={client.email || "Not set"} />
        <InfoCell label="Client Mobile Number" value={client.phone || "Not set"} />
        <InfoCell label="Project Created Date" value={dateShort(project?.created_at || project?.start_date)} />
        <InfoCell label="Project Updated Date" value={dateShort(project?.updated_at)} />
        <InfoCell label="Project Deadline" value={dateShort(project?.due_date)} />
        <InfoCell label="Project Renewal Date" value={dateShort(project?.renewal_date)} />
        <InfoCell label="Project Status" value={project?.status || "Not set"} badge />
        <InfoCell label="Project Priority" value={project?.priority || "Not set"} badge />
        <InfoCell label="Project Progress" value={pct(project?.progress)} />
        <InfoCell label="Total Cost" value={money(finance.total)} detail={`${summary.open} open tasks`} />
      </div>
    </div>
  );
}

function ProjectBlueprint({ project }) {
  return (
    <div className="panel p-4">
      <PanelHeading icon={Lightbulb} title="Project Blueprint" subtitle="Idea, technologies, features, and delivery scope." />
      <p className="mt-4 text-sm leading-6 text-slate-300">{project?.project_idea || project?.description || "No project idea added yet."}</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <ChipGroup label="Technologies" items={safeList(project?.technologies_used)} empty="None added." />
        <ChipGroup label="Features" items={safeList(project?.features_to_implement)} empty="None added." />
      </div>
    </div>
  );
}

function AssignedTeam({ project }) {
  const teams = project?.teams_detail || [];
  const developers = project?.developers_detail || [];
  return (
    <div className="panel p-4">
      <PanelHeading icon={UsersRound} title="Assigned Team" subtitle="Team leads, developers, and delivery ownership." />
      <div className="mt-4 space-y-2">
        {teams.map((team) => (
          <div key={`team-${team.id}`} className="flex items-center justify-between gap-3 rounded-lg border border-cyan-300/20 bg-cyan-300/10 px-3 py-2">
            <div>
              <p className="text-sm font-medium text-white">{team.name}</p>
              <p className="text-xs text-slate-500">{team.member_count}/{team.max_members} members</p>
            </div>
            <Badge value="TEAM" />
          </div>
        ))}
        {developers.map((developer) => (
          <div key={developer.id} className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.035] px-3 py-2">
            <div>
              <p className="text-sm font-medium text-white">{displayName(developer)}</p>
              <p className="text-xs text-slate-500">{developer.secret_id} / {developer.role_title || developer.department || "Developer"}</p>
            </div>
            <Badge value={`${developer.assigned_task_count || 0} Tasks`} />
          </div>
        ))}
        {!developers.length && !teams.length && <EmptyPanel text="No developers assigned yet." />}
      </div>
    </div>
  );
}

function TechnologyStack({ project }) {
  const stack = stackGroups(project);
  return (
    <div className="panel p-4">
      <PanelHeading icon={Code2} title="Project Technology Stack" subtitle="Frontend, backend, database, and cloud technologies." />
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {stack.map((group) => (
          <div key={group.label} className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
              <group.icon size={16} className="text-cyan-300" />
              {group.label}
            </div>
            <div className="flex flex-wrap gap-2">
              {group.items.length
                ? group.items.map((item) => <Badge key={item} value={item} />)
                : <span className="text-sm text-slate-500">Not selected</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function HostingSnapshot({ project, deployment }) {
  const urls = projectUrls(project);
  return (
    <div className="panel p-4">
      <PanelHeading icon={Globe2} title="Hosting and Deployment Snapshot" subtitle="Provider, live URLs, and latest deployment state." />
      <div className="mt-4 grid gap-3">
        <InfoRow label="Hosting Provider" value={project?.hosting_provider || "Not configured"} />
        <InfoRow label="Package" value={project?.hosting_package || "Not set"} />
        <InfoRow label="Deployment Toggle" value={deployment?.is_enabled ? "ON" : "OFF"} badge />
        <InfoRow label="Latest Status" value={project?.latest_deployment_status || "NOT_DEPLOYED"} badge />
        {urls.slice(0, 3).map((url) => <UrlRow key={url.label} {...url} />)}
      </div>
    </div>
  );
}

function ProjectFileManager({ project }) {
  return (
    <div className="panel p-4">
      <PanelHeading icon={Folder} title="Project File Manager" subtitle="Structured source, documents, deployments, and backup folders." />
      <div className="mt-4 overflow-hidden rounded-lg border border-white/10">
        {FILE_TREE.map((folder) => (
          <div key={folder.name} className="border-b border-white/10 bg-white/[0.025] last:border-b-0">
            <div className="flex items-center justify-between gap-3 px-3 py-3">
              <div className="flex items-center gap-2">
                <folder.icon size={16} className="text-cyan-300" />
                <span className="text-sm font-semibold text-white">{folder.name}</span>
              </div>
              <Badge value={project?.slug || "PROJECT"} />
            </div>
            <div className="grid gap-2 border-t border-white/10 bg-slate-950/35 px-6 py-3">
              {folder.children.map((child) => (
                <div key={child} className="flex items-center justify-between gap-3 text-sm">
                  <span className="flex items-center gap-2 text-slate-300">
                    {child.includes(".") ? <FileText size={14} className="text-slate-500" /> : <Folder size={14} className="text-slate-500" />}
                    {child}
                  </span>
                  <span className="text-xs text-slate-500">Version ready</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FinancialManagement({ finance }) {
  return (
    <div className="panel p-4">
      <PanelHeading icon={WalletCards} title="Financial Management" subtitle="Project pricing, GST, payment state, and pending amount." />
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <InfoCell label="Total Project Cost" value={money(finance.total)} />
        <InfoCell label="Paid Amount" value={money(finance.paid)} />
        <InfoCell label="Pending Amount" value={money(finance.pending)} />
        <InfoCell label="GST" value={money(finance.gst)} />
        <InfoCell label="Discount" value={money(finance.discount)} />
        <InfoCell label="Additional Charges" value={money(finance.additional)} />
      </div>
    </div>
  );
}

function HostingCenter({ project, deployment }) {
  const urls = projectUrls(project);
  return (
    <div className="panel p-4">
      <PanelHeading icon={Cloud} title="Hosting and Deployment Center" subtitle="Provider status, production links, staging links, and API endpoints." />
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <InfoCell label="Hosting Provider" value={project?.hosting_provider || "Not set"} />
        <InfoCell label="Deployment Status" value={project?.latest_deployment_status || "NOT_DEPLOYED"} badge />
        <InfoCell label="System Status" value={project?.system_status || "HEALTHY"} badge />
        <InfoCell label="Deployment Toggle" value={deployment?.is_enabled ? "ON" : "OFF"} badge />
      </div>
      <div className="mt-4 grid gap-3">
        {urls.map((url) => <UrlRow key={url.label} {...url} />)}
      </div>
    </div>
  );
}

function ActivityTimeline({ project, tasks, deployment }) {
  const rows = timelineRows(project, tasks, deployment);
  return (
    <div className="panel p-4">
      <PanelHeading icon={History} title="Activity Timeline" subtitle="Project, approval, deployment, commit, and task activity." />
      <div className="mt-4 space-y-3">
        {rows.map((item) => (
          <div key={`${item.time}-${item.title}`} className="flex gap-3">
            <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-[color:var(--accent)]" />
            <div className="min-w-0">
              <p className="text-sm font-semibold text-white">{item.title}</p>
              <p className="text-xs text-slate-500">{item.time}</p>
              {item.detail && <p className="mt-1 text-sm text-slate-400">{item.detail}</p>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TaskModal({ open, project, taskForm, setTaskForm, onClose, onSubmit }) {
  return (
    <Modal open={open} title="Create Task" onClose={onClose}>
      <form onSubmit={onSubmit} className="grid gap-4">
        <div>
          <label className="label">Title</label>
          <input className="field" required value={taskForm.title} onChange={(event) => setTaskForm({ ...taskForm, title: event.target.value })} />
        </div>
        <div>
          <label className="label">Description</label>
          <textarea className="field min-h-28" value={taskForm.description} onChange={(event) => setTaskForm({ ...taskForm, description: event.target.value })} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label">Priority</label>
            <select className="field" value={taskForm.priority} onChange={(event) => setTaskForm({ ...taskForm, priority: event.target.value })}>
              <option value="LOW">Low</option>
              <option value="MEDIUM">Medium</option>
              <option value="HIGH">High</option>
              <option value="CRITICAL">Critical</option>
            </select>
          </div>
          <div>
            <label className="label">Status</label>
            <select className="field" value={taskForm.status} onChange={(event) => setTaskForm({ ...taskForm, status: event.target.value })}>
              <option value="BACKLOG">Backlog</option>
              <option value="TODO">To Do</option>
              <option value="IN_PROGRESS">In Progress</option>
            </select>
          </div>
          <div>
            <label className="label">Workflow Day</label>
            <select className="field" value={taskForm.workflow_day} onChange={(event) => setTaskForm({ ...taskForm, workflow_day: Number(event.target.value) })}>
              {Array.from({ length: Math.min(project?.workflow_days || 7, 30) }, (_, index) => index + 1).map((day) => (
                <option key={day} value={day}>Day {day}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Assignee</label>
            <select className="field" value={taskForm.assignee} onChange={(event) => setTaskForm({ ...taskForm, assignee: event.target.value })}>
              <option value="">Unassigned</option>
              {(project?.developers_detail || []).map((developer) => <option key={developer.id} value={developer.id}>{displayName(developer)}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Due Date</label>
            <input className="field" type="date" value={taskForm.due_date} onChange={(event) => setTaskForm({ ...taskForm, due_date: event.target.value })} />
          </div>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/[0.035] p-3 text-sm text-slate-400">
          <span className="inline-flex items-center gap-2 text-slate-300"><ClipboardList size={15} /> Workflow chain</span>
          <span className="ml-2">Day 1 to Day {project?.workflow_days || 7}</span>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit"><Wrench size={16} />Create</Button>
        </div>
      </form>
    </Modal>
  );
}

function MetricTile({ icon: Icon, label, value, detail, badge }) {
  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between gap-3">
        <Icon size={18} className="text-cyan-300" />
        {badge && <Badge value={badge} />}
      </div>
      <p className="mt-3 text-xs uppercase tracking-[0.14em] text-slate-500">{label}</p>
      <p className="mt-1 truncate text-xl font-semibold text-white">{value}</p>
      {detail && <p className="mt-1 truncate text-xs text-slate-500">{detail}</p>}
    </div>
  );
}

function MiniStat({ icon: Icon, label, value }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
      <Icon size={17} className="text-cyan-300" />
      <p className="mt-2 text-xs uppercase tracking-[0.14em] text-slate-500">{label}</p>
      <p className="mt-1 truncate text-lg font-semibold text-white">{value}</p>
    </div>
  );
}

function PanelHeading({ icon: Icon, title, subtitle }) {
  return (
    <div>
      <div className="flex items-center gap-2 text-sm font-semibold text-white">
        <Icon size={17} className="text-cyan-300" />
        {title}
      </div>
      {subtitle && <p className="mt-1 text-sm text-slate-400">{subtitle}</p>}
    </div>
  );
}

function InfoCell({ label, value, detail, badge }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
      <p className="text-xs uppercase tracking-[0.14em] text-slate-500">{label}</p>
      <div className="mt-2">
        {badge ? <Badge value={value} /> : <p className="break-words text-sm font-semibold text-white">{value || "Not set"}</p>}
      </div>
      {detail && <p className="mt-1 text-xs text-slate-500">{detail}</p>}
    </div>
  );
}

function InfoRow({ label, value, badge }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.035] px-3 py-2">
      <span className="text-xs uppercase tracking-[0.14em] text-slate-500">{label}</span>
      <span className="min-w-0 text-right text-sm font-semibold text-white">
        {badge ? <Badge value={value} /> : value || "Not set"}
      </span>
    </div>
  );
}

function UrlRow({ label, url, status }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.035] px-3 py-2">
      <div className="min-w-0">
        <p className="text-xs uppercase tracking-[0.14em] text-slate-500">{label}</p>
        {url ? (
          <a href={url} target="_blank" rel="noreferrer" className="mt-1 block truncate text-sm font-semibold text-cyan-200 hover:text-cyan-100">
            {url}
          </a>
        ) : (
          <p className="mt-1 text-sm text-slate-500">Not configured</p>
        )}
      </div>
      <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${status === "Online" ? "bg-emerald-300" : status === "Maintenance" ? "bg-amber-300" : "bg-rose-300"}`} />
    </div>
  );
}

function ChipGroup({ label, items, empty }) {
  return (
    <div>
      <p className="label">{label}</p>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => <Badge key={item} value={item} />)}
        {!items.length && <span className="text-sm text-slate-500">{empty}</span>}
      </div>
    </div>
  );
}

function ProgressBar({ label, value }) {
  const safe = Math.max(0, Math.min(100, Math.round(Number(value || 0))));
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="text-slate-400">{label}</span>
        <span className="font-semibold text-white">{safe}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full bg-[color:var(--accent)]" style={{ width: `${safe}%` }} />
      </div>
    </div>
  );
}

function BackupRow({ name, date, size, user }) {
  return (
    <div className="grid gap-3 border-b border-white/10 bg-white/[0.025] px-3 py-2 text-sm last:border-b-0 md:grid-cols-[1fr_auto_auto_auto]">
      <span className="font-semibold text-white">{name}</span>
      <span className="text-slate-500">{dateShort(date)}</span>
      <span className="text-slate-500">{size}</span>
      <span className="text-slate-400">{displayName(user) || "System"}</span>
    </div>
  );
}

function EmptyPanel({ text }) {
  return (
    <div className="rounded-lg border border-dashed border-white/15 bg-white/[0.025] p-4 text-sm text-slate-500">
      {text}
    </div>
  );
}

function SparkIcon() {
  return <Lightbulb size={16} />;
}

function BrainIcon(props) {
  return <Bot {...props} />;
}

function safeList(value) {
  if (Array.isArray(value)) return value.filter(Boolean).map(String);
  if (typeof value === "string") return value.split(",").map((item) => item.trim()).filter(Boolean);
  return [];
}

function metadata(project) {
  const data = project?.lifecycle_metadata;
  return data && typeof data === "object" && !Array.isArray(data) ? data : {};
}

function metaGroup(project, key) {
  const value = metadata(project)[key];
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function asNumber(value) {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function money(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0
  }).format(asNumber(value));
}

function displayName(user) {
  if (!user) return "";
  return user.full_name || [user.first_name, user.last_name].filter(Boolean).join(" ") || user.username || user.email || "";
}

function projectCode(project) {
  if (!project?.id) return "PRJ-Loading";
  const year = new Date(project.created_at || Date.now()).getFullYear();
  return `PRJ-${year}-${String(project.id).padStart(5, "0")}`;
}

function projectFinance(project) {
  const finance = metaGroup(project, "finance");
  const base = asNumber(project?.project_cost || project?.budget);
  const hosting = asNumber(project?.hosting_cost);
  const renewal = asNumber(project?.renewal_cost);
  const discount = asNumber(finance.discount || finance.discount_amount);
  const additional = asNumber(finance.additional_charges || finance.additional);
  const gst = asNumber(finance.gst_amount ?? finance.gst ?? Math.round(base * 0.18));
  const paid = asNumber(finance.paid_amount || finance.paid);
  const total = Math.max(0, base + hosting + renewal + gst + additional - discount);
  const pending = Math.max(0, total - paid);
  const status = total > 0 && pending <= 0 ? "PAID" : pending > 0 ? "PENDING" : "DRAFT";
  return { base, hosting, renewal, discount, additional, gst, paid, total, pending, status };
}

function taskSummary(tasks) {
  const total = tasks.length;
  const done = tasks.filter((task) => task.status === "DONE").length;
  const blocked = tasks.filter((task) => task.status === "BLOCKED").length;
  return {
    total,
    done,
    blocked,
    open: tasks.filter((task) => !["DONE", "BLOCKED"].includes(task.status)).length
  };
}

function developerTaskCount(tasks, developerId) {
  if (!developerId) return 0;
  return tasks.filter((task) => task.assignee === developerId || task.assignee_detail?.id === developerId).length;
}

function stackGroups(project) {
  const technologies = safeList(project?.technologies_used);
  const lower = technologies.map((item) => item.toLowerCase());
  const groups = STACK_GROUPS.map((group) => ({
    ...group,
    items: technologies.filter((item, index) => group.keywords.some((keyword) => lower[index].includes(keyword)))
  }));
  const matched = new Set(groups.flatMap((group) => group.items));
  const other = technologies.filter((item) => !matched.has(item));
  return other.length ? [...groups, { label: "Other", icon: Layers, items: other }] : groups;
}

function projectUrls(project) {
  const urls = metaGroup(project, "urls");
  return [
    { label: "Production URL", url: project?.latest_deployment_url || project?.hosted_url || urls.production, status: urlStatus(project) },
    { label: "Staging URL", url: urls.staging, status: "Maintenance" },
    { label: "Development URL", url: project?.local_url || urls.development, status: project?.local_url ? "Online" : "Offline" },
    { label: "Admin URL", url: urls.admin || urls.admin_url, status: urls.admin || urls.admin_url ? "Online" : "Offline" },
    { label: "API URL", url: urls.api || urls.api_url, status: urls.api || urls.api_url ? "Online" : "Offline" }
  ];
}

function urlStatus(project) {
  if (["HEALTHY", "ACTIVE", "DEPLOYED"].includes(project?.system_status || project?.latest_deployment_status)) return "Online";
  if (project?.system_status === "MAINTENANCE") return "Maintenance";
  return project?.hosted_url || project?.latest_deployment_url ? "Online" : "Offline";
}

function sslLabel(project) {
  const ssl = project?.ssl_info || {};
  if (ssl.valid || ssl.status === "valid") return "Valid";
  if (ssl.expires_at) return `Expires ${dateShort(ssl.expires_at)}`;
  return "Not configured";
}

function messageRows(project, suggestions, channel) {
  const client = project?.client_detail;
  const updated = dateShort(project?.updated_at);
  const rows = {
    client: [
      {
        author: displayName(client) || "Client",
        time: updated,
        text: project?.description || "No client message recorded for this project."
      }
    ],
    admin: [
      {
        author: displayName(project?.owner_detail) || "Admin",
        time: dateShort(project?.approved_at || project?.updated_at),
        text: project?.approval_note || "Project review notes will appear here."
      }
    ],
    developer: (project?.developers_detail || []).slice(0, 3).map((developer) => ({
      author: displayName(developer),
      time: updated,
      text: `${developer.role_title || developer.department || "Developer"} assigned to delivery.`
    })),
    ai: suggestions.slice(0, 4).map((suggestion) => ({
      author: "AI Assistant",
      time: updated,
      text: suggestion.rationale || suggestion.title
    }))
  };
  return rows[channel]?.length ? rows[channel] : [{ author: "System", time: updated, text: "No messages in this lane yet." }];
}

function riskLevel(project, tasks) {
  const summary = taskSummary(tasks);
  const health = Number(project?.health_score || 100);
  if (summary.blocked || health < 60) return "HIGH";
  if (summary.open > 8 || Number(project?.progress || 0) < 35) return "MEDIUM";
  return "LOW";
}

function aiAnalysis(project, tasks) {
  const features = safeList(project?.features_to_implement);
  const tech = safeList(project?.technologies_used);
  const openTasks = taskSummary(tasks).open;
  const days = estimateDays(project, openTasks);
  return {
    days,
    risk: riskLevel(project, tasks),
    developers: Math.max(1, Math.min(6, Math.ceil(openTasks / 5) || (project?.developers_detail?.length || 1))),
    missingModules: Math.max(0, 4 - Math.min(4, features.length + Math.floor(tech.length / 2)))
  };
}

function estimateDays(project, openTasks) {
  if (project?.due_date) {
    const diff = new Date(project.due_date).getTime() - Date.now();
    if (Number.isFinite(diff) && diff > 0) return Math.max(1, Math.ceil(diff / 86400000));
  }
  return Math.max(1, openTasks * 2 || Number(project?.workflow_days || 7));
}

function timelineRows(project, tasks, deployment) {
  const latestTask = [...tasks].sort((a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0))[0];
  return [
    {
      title: "Project created",
      time: dateShort(project?.created_at || project?.start_date),
      detail: project?.project_idea || project?.description
    },
    {
      title: `Approval status: ${String(project?.approval_status || "DRAFT").replaceAll("_", " ")}`,
      time: dateShort(project?.approved_at || project?.updated_at),
      detail: project?.approval_note
    },
    {
      title: "Latest deployment",
      time: dateShort(project?.latest_deployment_at),
      detail: project?.latest_deployment_status || (deployment?.is_enabled ? "Deployment enabled" : "Deployment disabled")
    },
    {
      title: "Latest commit",
      time: dateShort(project?.last_commit_at),
      detail: project?.last_commit_message || "No commits synced yet."
    },
    {
      title: latestTask ? `Task updated: ${latestTask.title}` : "Task activity",
      time: dateShort(latestTask?.updated_at),
      detail: latestTask ? latestTask.status : "No task updates yet."
    }
  ];
}
