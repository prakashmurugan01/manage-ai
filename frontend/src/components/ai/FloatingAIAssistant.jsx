import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Bot, CheckCircle2, ChevronDown, FileUp, Loader2, Mic, MicOff, PauseCircle, Send, Sparkles, Volume2, VolumeX, X, Zap } from "lucide-react";

import { aiApi, deploymentsApi, notificationsApi, projectsApi, ticketsApi, usersApi } from "../../api/services.js";
import { apiErrorMessage } from "../../api/client.js";
import { useAuth } from "../../context/AuthContext.jsx";

const quickCommands = ["Create ticket", "Deploy my project", "Show active projects", "Show latest alerts", "Approve user", "Server health"];
const providers = [
  ["gemini", "Gemini"],
  ["auto", "Auto Router"],
  ["local", "Local"]
];

export default function FloatingAIAssistant() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState(() => [
    {
      id: "hello",
      role: "ASSISTANT",
      content: `Hey ${user?.first_name || user?.full_name || "there"}! I'm ManageAI Assistant. Ask in English, Tamil, or mixed Tamil-English. I can help with hosting, deployments, files, tickets, and server health.`,
      metadata: { provider_used: "gemini" }
    }
  ]);
  const [input, setInput] = useState("");
  const [files, setFiles] = useState([]);
  const [provider, setProvider] = useState("gemini");
  const [speakerOn, setSpeakerOn] = useState(true);
  const [muted, setMuted] = useState(false);
  const [listening, setListening] = useState(false);
  const [continuousListening, setContinuousListening] = useState(false);
  const [assistantState, setAssistantState] = useState("idle");
  const [actionDraft, setActionDraft] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef(null);
  const fileRef = useRef(null);
  const recognitionRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, open]);

  const sendMessage = async (text = input) => {
    const clean = (text || "").trim();
    if (!clean && !files.length) return;
    const localUserMessage = { id: `u-${Date.now()}`, role: "USER", content: clean || `Uploaded ${files.length} file(s)` };
    setMessages((items) => [...items, localUserMessage]);
    setInput("");
    setError("");
    setAssistantState("processing");
    setLoading(true);
    try {
      const handled = await handleActionCommand(clean);
      if (handled) return;
      const form = new FormData();
      form.append("message", clean || "Analyze these uploaded files and provide deployment-ready guidance.");
      form.append("mode", inferMode(clean));
      form.append("model_provider", provider);
      form.append("model_name", provider === "auto" ? "smart-router" : `${provider}-router`);
      if (sessionId) form.append("session", String(sessionId));
      files.forEach((file) => form.append("files", file));
      const { data } = await aiApi.assistantChat(form);
      setSessionId(data.session.id);
      setFiles([]);
      const assistant = {
        ...data.assistant_message,
        content: data.assistant_message.content,
        metadata: {
          ...(data.assistant_message.metadata || {}),
          provider_used: data.provider_used,
          fallback_used: data.fallback_used
        }
      };
      setMessages((items) => [...items, assistant]);
      if (speakerOn && !muted) speak(assistant.content);
    } catch (err) {
      setError(apiErrorMessage(err, "AI Assistant is not responding."));
    } finally {
      setLoading(false);
      setAssistantState("idle");
    }
  };

  const addAssistantMessage = (content, metadata = {}) => {
    const message = {
      id: `a-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      role: "ASSISTANT",
      content,
      metadata: { provider_used: "action-engine", ...metadata }
    };
    setMessages((items) => [...items, message]);
    if (speakerOn && !muted) speak(content);
  };

  const handleActionCommand = async (text) => {
    const value = text.toLowerCase();
    const intent = detectActionIntent(value);
    if (/^(cancel|stop|reset|clear action)$/i.test(value) && actionDraft) {
      setActionDraft(null);
      addAssistantMessage("Action cancelled. You can start a new ticket, deployment, approval, or live data request.");
      return true;
    }
    if (actionDraft) {
      if (intent && intent !== actionDraft.type) {
        setActionDraft(null);
        return runActionIntent(intent, text);
      }
      await continueAction(actionDraft, text);
      return true;
    }
    if (intent) return runActionIntent(intent, text);
    return false;
  };

  const runActionIntent = async (intent, text) => {
    if (intent === "ticket") {
      const draft = { type: "ticket", data: extractTicketFields(text) };
      setActionDraft(draft);
      await continueAction(draft, "");
      return true;
    }
    if (intent === "deploy") {
      const draft = { type: "deploy", data: extractDeployFields(text) };
      setActionDraft(draft);
      await continueAction(draft, "");
      return true;
    }
    if (intent === "active_projects") {
      const { data } = await projectsApi.list({ status: "ACTIVE" });
      const projects = normalizeList(data).slice(0, 8);
      addAssistantMessage(projects.length ? `Active projects:\n${projects.map((project) => `• #${project.id} ${project.name} · ${project.progress}% · ${project.system_status || project.status}`).join("\n")}` : "No active projects found.");
      return true;
    }
    if (intent === "alerts") {
      const { data } = await notificationsApi.list();
      const alerts = normalizeList(data).slice(0, 6);
      addAssistantMessage(alerts.length ? `Latest alerts:\n${alerts.map((item) => `• ${item.title} · ${item.urgency || item.type}${item.is_read ? "" : " · unread"}`).join("\n")}` : "No alerts found.");
      return true;
    }
    if (intent === "approve_user") {
      const draft = { type: "approve_user", data: extractUserApprovalFields(text) };
      setActionDraft(draft);
      await continueAction(draft, "");
      return true;
    }
    return false;
  };

  const continueAction = async (draft, text) => {
    const data = mergeActionInput(draft, text);
    if (draft.type === "ticket") return createTicketAction(data);
    if (draft.type === "deploy") return deployAction(data);
    if (draft.type === "approve_user") return approveUserAction(data);
  };

  const createTicketAction = async (data) => {
    const missing = ["project", "title", "description"].filter((key) => !data[key]);
    if (missing.length) {
      setActionDraft({ type: "ticket", data });
      addAssistantMessage(`I can create the ticket. Please provide: ${missing.join(", ")}.\nExample: project 12, title Login error, description Users cannot sign in, priority HIGH.`);
      return;
    }
    const project = await resolveProject(data.project);
    if (!project) {
      setActionDraft({ type: "ticket", data: { ...data, project: "" } });
      addAssistantMessage("I could not find that project. Send a project ID or exact project name.");
      return;
    }
    const form = new FormData();
    form.append("project", project.id);
    form.append("title", data.title);
    form.append("description", data.description);
    form.append("priority", data.priority || "P3");
    form.append("type", "INCIDENT");
    const { data: ticket } = await ticketsApi.create(form);
    setActionDraft(null);
    addAssistantMessage(`Ticket created and saved.\nTicket number: ${ticket.ticket_id}\nTitle: ${ticket.title}\nProject: ${ticket.project_name || project.name}\nStatus: ${ticket.status}`);
  };

  const deployAction = async (data) => {
    if (!data.project) {
      setActionDraft({ type: "deploy", data });
      addAssistantMessage("I can deploy it. Which project should I deploy? Send project ID or project name. Optional: branch main, version v1.0.0, environment production.");
      return;
    }
    const project = await resolveProject(data.project);
    if (!project) {
      setActionDraft({ type: "deploy", data: { ...data, project: "" } });
      addAssistantMessage("I could not find that project. Send a project ID or exact project name.");
      return;
    }
    const { data: deployments } = await deploymentsApi.list({ project: project.id });
    const controls = normalizeList(deployments);
    const control = controls.find((item) => (item.environment || "").toLowerCase() === (data.environment || "production").toLowerCase()) || controls[0];
    if (!control) {
      setActionDraft(null);
      addAssistantMessage(`No deployment control exists for ${project.name}. Open Deployment Center once to create a deployment target, then I can trigger it.`);
      return;
    }
    const payload = {
      is_enabled: true,
      source_branch: data.branch || project.selected_branch || project.github_default_branch || "main",
      version: data.version || "",
      notes: "Triggered by ManageAI Assistant"
    };
    const { data: result } = await deploymentsApi.toggle(control.id, payload);
    setActionDraft(null);
    addAssistantMessage(`Deployment triggered.\nProject: ${result.project_name || project.name}\nEnvironment: ${result.environment}\nBranch: ${result.source_branch || payload.source_branch}\nStatus: ${result.status}\nEnabled: ${result.is_enabled ? "Yes" : "No"}`);
  };

  const approveUserAction = async (data) => {
    if (!data.user) {
      const { data: pendingData } = await usersApi.list({ approval_status: "PENDING" });
      const pending = normalizeList(pendingData).slice(0, 6);
      setActionDraft({ type: "approve_user", data });
      addAssistantMessage(pending.length ? `Which user should I approve?\n${pending.map((item) => `• #${item.id} ${item.email} · ${item.role}`).join("\n")}\nReply with user ID or email.` : "No pending users found.");
      return;
    }
    const user = await resolveUser(data.user);
    if (!user) {
      setActionDraft({ type: "approve_user", data: { user: "" } });
      addAssistantMessage("I could not find that user. Send a pending user's ID or email.");
      return;
    }
    const { data: approved } = await usersApi.approve(user.id);
    setActionDraft(null);
    addAssistantMessage(`User approved.\n${approved.full_name || approved.email}\nRole: ${approved.role}\nStatus: ${approved.approval_status}`);
  };

  const resolveProject = async (query) => {
    if (!query) return null;
    if (/^\d+$/.test(String(query))) {
      const { data } = await projectsApi.get(query);
      return data;
    }
    const { data } = await projectsApi.list({ search: query });
    return normalizeList(data).find((item) => item.name?.toLowerCase() === String(query).toLowerCase()) || normalizeList(data)[0];
  };

  const resolveUser = async (query) => {
    const { data } = await usersApi.list({ search: query, approval_status: "PENDING" });
    return normalizeList(data).find((item) => String(item.id) === String(query) || item.email?.toLowerCase() === String(query).toLowerCase()) || normalizeList(data)[0];
  };

  const startVoice = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setError("Voice input is not available in this browser.");
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = "en-IN";
    recognition.interimResults = true;
    recognition.continuous = continuousListening;
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results).map((item) => item[0]?.transcript || "").join(" ");
      setInput(transcript);
    };
    recognition.onend = () => {
      setListening(false);
      setAssistantState("idle");
    };
    recognition.start();
    recognitionRef.current = recognition;
    setListening(true);
    setAssistantState("listening");
  };

  const stopVoice = () => {
    recognitionRef.current?.stop();
    setListening(false);
    setAssistantState("idle");
  };

  const speak = (text) => {
    if (!window.speechSynthesis || !text) return;
    setAssistantState("speaking");
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text.replace(/[#*_`>-]/g, " "));
    utterance.lang = /[\u0B80-\u0BFF]/.test(text) ? "ta-IN" : "en-IN";
    utterance.rate = 1;
    utterance.onend = () => setAssistantState("idle");
    window.speechSynthesis.speak(utterance);
  };

  const toggleMute = () => {
    const nextMuted = !muted;
    setMuted(nextMuted);
    if (nextMuted) {
      window.speechSynthesis?.cancel();
      setAssistantState("idle");
    }
  };

  return (
    <>
      <AnimatePresence>
        {open && (
          <motion.section
            initial={{ opacity: 0, y: 30, scale: 0.94 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.96 }}
            transition={{ type: "spring", stiffness: 260, damping: 24 }}
            className="fixed bottom-24 right-5 z-50 flex h-[min(720px,calc(100vh-7rem))] w-[min(520px,calc(100vw-1.5rem))] flex-col overflow-hidden rounded-[1.75rem] border border-violet-300/25 bg-slate-950/95 shadow-2xl shadow-violet-950/50 backdrop-blur-2xl"
          >
            <div className="relative overflow-hidden bg-gradient-to-r from-violet-700 via-indigo-600 to-fuchsia-600 p-5">
              <div className="absolute inset-0 opacity-30 [background:radial-gradient(circle_at_20%_0%,white,transparent_32%)]" />
              <div className="relative flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="grid h-14 w-14 place-items-center rounded-2xl border border-white/25 bg-white/15 text-white shadow-lg">
                    <Bot size={26} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-xl font-black text-white">ManageAI</h2>
                      <span className="rounded-full bg-white/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.16em] text-violet-100">Assistant</span>
                    </div>
                    <p className="text-sm text-violet-100">OpenAI + Gemini smart router</p>
                  </div>
                </div>
                <button type="button" onClick={() => setOpen(false)} className="rounded-xl bg-white/10 p-2 text-white hover:bg-white/20" aria-label="Close assistant">
                  <ChevronDown size={18} />
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between gap-2 border-b border-white/10 bg-white/[0.03] px-4 py-3">
              <select value={provider} onChange={(event) => setProvider(event.target.value)} className="rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-xs font-semibold text-slate-100 outline-none">
                {providers.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <Zap size={14} className="text-cyan-300" />
                Tamil + English ready
              </div>
            </div>

            <div className="border-b border-white/10 bg-slate-950/80 px-4 py-2">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                {["listening", "processing", "speaking"].map((state) => (
                  <span key={state} className={`rounded-full border px-2.5 py-1 font-semibold capitalize ${assistantState === state ? "border-cyan-300/50 bg-cyan-300/15 text-cyan-100" : "border-white/10 bg-white/[0.03] text-slate-500"}`}>
                    {state}
                  </span>
                ))}
                {actionDraft && <span className="ml-auto rounded-full border border-amber-300/30 bg-amber-300/10 px-2.5 py-1 font-semibold text-amber-100">Action: {actionDraft.type.replace("_", " ")}</span>}
              </div>
            </div>

            <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
              {messages.map((message) => <Bubble key={message.id} message={message} onSpeak={speak} />)}
              {loading && (
                <div className="flex items-center gap-2 rounded-2xl border border-violet-300/20 bg-violet-300/10 p-3 text-sm text-violet-100">
                  <Loader2 className="animate-spin" size={16} /> Thinking, routing model, checking workspace context...
                </div>
              )}
              {error && <div className="rounded-2xl border border-red-300/25 bg-red-400/10 p-3 text-sm text-red-100">{error}</div>}
              <div ref={endRef} />
            </div>

            <div className="border-t border-white/10 bg-slate-950/95 p-4">
              <div className="mb-3 flex flex-wrap gap-2">
                {quickCommands.map((command) => (
                  <button key={command} type="button" onClick={() => sendMessage(command)} className="rounded-full border border-violet-300/25 bg-violet-300/10 px-3 py-1.5 text-xs font-semibold text-violet-100 hover:border-violet-200/60">
                    {command}
                  </button>
                ))}
              </div>
              {files.length ? <p className="mb-2 truncate text-xs text-slate-400">{files.map((file) => file.name).join(", ")}</p> : null}
              <div className="flex items-center gap-2">
                <input
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      sendMessage();
                    }
                  }}
                  placeholder="Type Tamil, English, logs, commands..."
                  className="min-w-0 flex-1 rounded-2xl border border-violet-300/35 bg-slate-950 px-4 py-3 text-sm text-white outline-none focus:border-violet-200"
                />
                <input ref={fileRef} type="file" multiple className="hidden" onChange={(event) => setFiles(Array.from(event.target.files || []))} />
                <button type="button" onClick={() => fileRef.current?.click()} className="rounded-2xl border border-white/10 bg-white/[0.04] p-3 text-slate-200 hover:border-violet-300/40" title="Upload files">
                  <FileUp size={18} />
                </button>
                <button type="button" onClick={listening ? stopVoice : startVoice} className={`rounded-2xl p-3 text-white ${listening ? "bg-red-500" : "bg-violet-600 hover:bg-violet-500"}`} title="Voice input">
                  {listening ? <MicOff size={18} /> : <Mic size={18} />}
                </button>
                <button type="button" onClick={() => sendMessage()} disabled={loading} className="rounded-2xl bg-violet-600 p-3 text-white hover:bg-violet-500 disabled:opacity-50" title="Send">
                  {loading ? <Loader2 className="animate-spin" size={18} /> : <Send size={18} />}
                </button>
              </div>
              <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                <button type="button" onClick={() => setContinuousListening((value) => !value)} className="inline-flex items-center gap-1 text-slate-400 hover:text-violet-200">
                  {continuousListening ? <CheckCircle2 size={13} /> : <PauseCircle size={13} />} Continuous {continuousListening ? "On" : "Off"}
                </button>
                <div className="flex items-center gap-3">
                  <button type="button" onClick={() => setSpeakerOn((value) => !value)} className="inline-flex items-center gap-1 text-violet-200">
                    {speakerOn ? <Volume2 size={13} /> : <VolumeX size={13} />} Speaker {speakerOn ? "On" : "Off"}
                  </button>
                  <button type="button" onClick={toggleMute} className="inline-flex items-center gap-1 text-violet-200">
                    {muted ? <VolumeX size={13} /> : <Volume2 size={13} />} {muted ? "Unmute" : "Mute"}
                  </button>
                </div>
              </div>
            </div>
          </motion.section>
        )}
      </AnimatePresence>

      <motion.button
        type="button"
        onClick={() => setOpen((value) => !value)}
        whileHover={{ scale: 1.06, y: -3 }}
        whileTap={{ scale: 0.95 }}
        className={`group fixed bottom-5 right-5 z-50 grid h-20 w-20 place-items-center overflow-visible rounded-[1.35rem] text-white shadow-2xl transition ${
          open ? "bg-gradient-to-br from-red-500 to-rose-600 shadow-red-950/50" : "bg-gradient-to-br from-indigo-500 via-violet-600 to-fuchsia-600 shadow-violet-950/50"
        }`}
        aria-label="Open AI assistant"
      >
        {!open && (
          <>
            <span className="pointer-events-none absolute -inset-2 rounded-[1.65rem] bg-violet-500/22 blur-xl transition group-hover:bg-fuchsia-400/30" />
            <span className="pointer-events-none absolute inset-0 rounded-[1.35rem] bg-[radial-gradient(circle_at_28%_18%,rgba(255,255,255,0.34),transparent_30%)]" />
            <motion.span
              className="pointer-events-none absolute -inset-1 rounded-[1.55rem] border border-cyan-200/30"
              animate={{ scale: [1, 1.1, 1], opacity: [0.45, 0.05, 0.45] }}
              transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
            />
            <motion.span
              className="pointer-events-none absolute -right-1 -top-1 grid h-6 w-6 place-items-center rounded-full border border-white/30 bg-slate-950 text-cyan-100 shadow-lg"
              animate={{ rotate: [0, 8, -8, 0], scale: [1, 1.08, 1] }}
              transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
            >
              <Sparkles size={14} />
            </motion.span>
            <span className="absolute bottom-2 right-2 h-3 w-3 rounded-full border-2 border-white bg-emerald-300 shadow-[0_0_16px_rgba(52,211,153,0.85)]" />
          </>
        )}
        <span className="pointer-events-none absolute right-[5.75rem] top-1/2 hidden -translate-y-1/2 whitespace-nowrap rounded-lg border border-violet-300/25 bg-slate-950/90 px-3 py-2 text-xs font-bold text-violet-100 opacity-0 shadow-xl backdrop-blur-xl transition group-hover:opacity-100 sm:block">
          {open ? "Close assistant" : "Ask ManageAI"}
        </span>
        {open ? (
          <X className="relative" size={30} />
        ) : (
          <motion.div
            className="relative grid h-12 w-12 place-items-center rounded-2xl border border-white/20 bg-white/12 shadow-inner"
            animate={{ y: [0, -2, 0] }}
            transition={{ duration: 2.8, repeat: Infinity, ease: "easeInOut" }}
          >
            <Bot size={30} />
          </motion.div>
        )}
      </motion.button>
    </>
  );
}

function Bubble({ message, onSpeak }) {
  const assistant = message.role === "ASSISTANT";
  const provider = message.metadata?.provider_used || message.metadata?.model_provider || "local";
  return (
    <div className={`flex ${assistant ? "justify-start" : "justify-end"}`}>
      <div className={`max-w-[82%] rounded-2xl border px-4 py-3 text-sm leading-relaxed ${assistant ? "border-white/10 bg-white/[0.055] text-slate-100" : "border-violet-300/35 bg-violet-600 text-white"}`}>
        {assistant && (
          <div className="mb-2 flex items-center justify-between gap-3">
            <span className="text-[10px] font-black uppercase tracking-[0.18em] text-violet-300">ManageAI · {provider}</span>
            <button type="button" onClick={() => onSpeak?.(message.content)} className="text-violet-200" title="Speak">
              <Volume2 size={13} />
            </button>
          </div>
        )}
        <div className="whitespace-pre-wrap break-words">{message.content}</div>
      </div>
    </div>
  );
}

function inferMode(text) {
  const value = (text || "").toLowerCase();
  if (/deploy|hosting|ssl|domain|vercel|netlify|aws|gemini|openai/.test(value)) return "HOSTING";
  if (/server|cpu|ram|disk|uptime|monitor/.test(value)) return "DEVOPS";
  if (/ticket|support|issue|bug/.test(value)) return "SUPPORT";
  if (/file|zip|pdf|screenshot|analyze/.test(value)) return "FILES";
  return "GENERAL";
}

function normalizeList(data) {
  if (Array.isArray(data)) return data;
  return data?.results || data?.items || [];
}

function extractTicketFields(text) {
  return {
    project: matchValue(text, /project\s*[:#-]?\s*([^,;]+)/i),
    title: matchValue(text, /title\s*[:#-]?\s*([^,;]+)/i),
    description: matchValue(text, /description\s*[:#-]?\s*([^;]+)/i),
    priority: normalizePriority(matchValue(text, /priority\s*[:#-]?\s*(critical|high|medium|low|p1|p2|p3|p4)/i))
  };
}

function extractDeployFields(text) {
  return {
    project: matchValue(text, /project\s*[:#-]?\s*([^,;]+)/i),
    branch: matchValue(text, /branch\s*[:#-]?\s*([^\s,;]+)/i),
    version: matchValue(text, /version\s*[:#-]?\s*([^\s,;]+)/i),
    environment: matchValue(text, /environment\s*[:#-]?\s*([^\s,;]+)/i)
  };
}

function extractUserApprovalFields(text) {
  return {
    user: matchValue(text, /(?:user|email|id)\s*[:#-]?\s*([^\s,;]+)/i)
  };
}

function mergeActionInput(draft, text) {
  const next = { ...(draft.data || {}) };
  if (draft.type === "ticket") {
    Object.assign(next, extractTicketFields(text));
    const clean = text.trim();
    if (clean && !hasLabeledField(clean)) {
      if (!next.project && /^\d+$/.test(clean)) next.project = clean;
      else if (!next.title) next.title = clean;
      else if (!next.description) next.description = clean;
    }
  }
  if (draft.type === "deploy") {
    Object.assign(next, extractDeployFields(text));
    const clean = text.trim();
    if (clean && !hasLabeledField(clean) && !next.project) next.project = clean;
  }
  if (draft.type === "approve_user") Object.assign(next, extractUserApprovalFields(text));
  if (text && draft.type === "approve_user" && !next.user) next.user = text.trim();
  return next;
}

function detectActionIntent(value) {
  if (/create (a )?ticket|new ticket|raise ticket/.test(value)) return "ticket";
  if (/deploy|deployment/.test(value)) return "deploy";
  if (/active projects|show projects|project list/.test(value)) return "active_projects";
  if (/latest alerts|show alerts|notifications|alerts/.test(value)) return "alerts";
  if (/approve user|approve account|user approval/.test(value)) return "approve_user";
  return "";
}

function hasLabeledField(text) {
  return /\b(project|title|description|priority|branch|version|environment|user|email|id)\s*[:#-]?/i.test(text);
}

function matchValue(text, regex) {
  return (text.match(regex)?.[1] || "").trim();
}

function normalizePriority(value) {
  const next = (value || "").toUpperCase();
  return { CRITICAL: "P1", HIGH: "P2", MEDIUM: "P3", LOW: "P4" }[next] || next;
}
