import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  Brain,
  Cloud,
  Code2,
  FileUp,
  Headphones,
  Loader2,
  Mic,
  MicOff,
  PlayCircle,
  Send,
  ShieldCheck,
  Sparkles,
  Volume2,
  VolumeX
} from "lucide-react";

import { aiApi } from "../api/services.js";
import { apiErrorMessage } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import { ROLE_LABELS } from "../utils/rbac.js";

const modes = [
  { value: "GENERAL", label: "Universal", icon: Brain },
  { value: "HOSTING", label: "Hosting", icon: Cloud },
  { value: "DEVOPS", label: "DevOps", icon: PlayCircle },
  { value: "PROJECT", label: "Project", icon: Code2 },
  { value: "SUPPORT", label: "Support", icon: Headphones },
  { value: "FILES", label: "Files", icon: FileUp },
  { value: "AUTOMATION", label: "Automation", icon: Sparkles }
];

const modelOptions = [
  ["local", "ManageAI Local"],
  ["openai", "GPT"],
  ["anthropic", "Claude"],
  ["google", "Gemini"],
  ["deepseek", "DeepSeek"],
  ["ollama", "Ollama"],
  ["huggingface", "HuggingFace"]
];

export default function AIAssistant() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const [sessionId, setSessionId] = useState(null);
  const [mode, setMode] = useState("GENERAL");
  const [provider, setProvider] = useState("local");
  const [message, setMessage] = useState("");
  const [files, setFiles] = useState([]);
  const [speak, setSpeak] = useState(true);
  const [listening, setListening] = useState(false);
  const [events, setEvents] = useState([]);
  const recognitionRef = useRef(null);
  const endRef = useRef(null);

  const sessions = useQuery({
    queryKey: ["assistant-sessions"],
    queryFn: () => aiApi.assistantSessions().then((r) => r.data.results || r.data)
  });

  const messages = useQuery({
    queryKey: ["assistant-messages", sessionId],
    queryFn: () => aiApi.assistantMessages(sessionId).then((r) => r.data),
    enabled: Boolean(sessionId)
  });

  const policy = useQuery({
    queryKey: ["assistant-role-policy"],
    queryFn: () => aiApi.assistantRolePolicy().then((r) => r.data)
  });

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.data, sessionId]);

  const activeMessages = messages.data || [];
  const currentPolicy = policy.data?.roles?.[user?.role] || {};

  const chat = useMutation({
    mutationFn: async () => {
      const payload = new FormData();
      payload.append("message", message);
      payload.append("mode", mode);
      payload.append("model_provider", provider);
      payload.append("model_name", provider === "local" ? "manageai-enterprise-local" : `${provider}-router`);
      payload.append("voice", String(Boolean(listening)));
      payload.append("speak", String(Boolean(speak)));
      if (sessionId) payload.append("session", String(sessionId));
      files.forEach((file) => payload.append("files", file));
      return aiApi.assistantChat(payload);
    },
    onSuccess: ({ data }) => {
      setSessionId(data.session.id);
      setMessage("");
      setFiles([]);
      setEvents((prev) => [{ title: "Assistant response", detail: data.intent }, ...prev].slice(0, 8));
      qc.invalidateQueries({ queryKey: ["assistant-sessions"] });
      qc.invalidateQueries({ queryKey: ["assistant-messages", data.session.id] });
      if (speak) speakText(data.assistant_message.content);
    },
    onError: (error) => setEvents((prev) => [{ title: "Assistant error", detail: apiErrorMessage(error, "Assistant request failed.") }, ...prev].slice(0, 8))
  });

  const canSend = message.trim() || files.length;

  const startVoice = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setEvents((prev) => [{ title: "Voice unavailable", detail: "This browser does not expose speech recognition." }, ...prev].slice(0, 8));
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results).map((item) => item[0]?.transcript || "").join(" ");
      setMessage(transcript);
    };
    recognition.onend = () => setListening(false);
    recognition.start();
    recognitionRef.current = recognition;
    setListening(true);
  };

  const stopVoice = () => {
    recognitionRef.current?.stop();
    setListening(false);
  };

  const speakText = (text) => {
    if (!window.speechSynthesis || !text) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text.replace(/[#*_`>-]/g, ""));
    utterance.rate = 1;
    utterance.pitch = 1;
    window.speechSynthesis.speak(utterance);
  };

  const stopSpeech = () => window.speechSynthesis?.cancel();

  const visibleSessions = useMemo(() => (sessions.data || []).slice(0, 8), [sessions.data]);

  return (
    <div className="space-y-5 text-[color:var(--text)]">
      <section className="relative overflow-hidden rounded-lg border border-cyan-300/15 bg-slate-950/70 p-5 shadow-2xl shadow-cyan-950/20">
        <div className="pointer-events-none absolute inset-0 cyber-grid opacity-25" />
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-cyan-200">
              <Bot size={22} />
              <span className="text-xs font-black uppercase tracking-[0.18em]">Enterprise AI Command Center</span>
            </div>
            <h1 className="mt-3 text-3xl font-black text-white">Role-aware AI assistant, voice desk, and project control engine</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-400">
              Context memory, file analysis, hosting guidance, deployment planning, support triage, and speaker output in one workspace.
            </p>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/[0.04] p-3 text-sm">
            <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Current role</p>
            <p className="mt-1 font-semibold text-white">{ROLE_LABELS[user?.role] || user?.role || "Guest Viewer"}</p>
            <p className="mt-1 text-xs text-slate-400">{currentPolicy.dashboard || "Read-only assistant"}</p>
          </div>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)_320px]">
        <aside className="rounded-lg border border-white/10 bg-slate-950/60 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold text-white">Sessions</h2>
            <button type="button" onClick={() => setSessionId(null)} className="rounded-md border border-cyan-300/25 bg-cyan-300/10 px-2 py-1 text-xs text-cyan-100">New</button>
          </div>
          <div className="space-y-2">
            {visibleSessions.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setSessionId(item.id)}
                className={`block w-full rounded-md border p-3 text-left text-sm transition ${sessionId === item.id ? "border-cyan-300/50 bg-cyan-300/10" : "border-white/10 bg-white/[0.025] hover:border-white/25"}`}
              >
                <p className="truncate font-medium text-white">{item.title}</p>
                <p className="mt-1 truncate text-xs text-slate-500">{item.last_message || item.mode}</p>
              </button>
            ))}
            {!visibleSessions.length && <p className="rounded-md border border-dashed border-white/10 p-3 text-xs text-slate-500">No assistant memory yet.</p>}
          </div>
        </aside>

        <main className="rounded-lg border border-white/10 bg-slate-950/60 p-4">
          <div className="mb-4 flex flex-wrap gap-2">
            {modes.map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                type="button"
                onClick={() => setMode(value)}
                className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-xs font-semibold ${mode === value ? "border-cyan-300/50 bg-cyan-300/15 text-cyan-50" : "border-white/10 bg-white/[0.03] text-slate-300"}`}
              >
                <Icon size={14} /> {label}
              </button>
            ))}
          </div>

          <div className="min-h-[460px] space-y-3 overflow-y-auto rounded-lg border border-white/10 bg-slate-950 p-3">
            {activeMessages.map((item) => (
              <MessageBubble key={item.id} message={item} onSpeak={speakText} />
            ))}
            {chat.isPending && (
              <div className="flex items-center gap-2 rounded-lg border border-cyan-300/20 bg-cyan-300/10 p-3 text-sm text-cyan-100">
                <Loader2 className="animate-spin" size={16} /> Thinking across projects, hosting, tickets, files, and role policy...
              </div>
            )}
            {!activeMessages.length && (
              <div className="grid min-h-[420px] place-items-center text-center">
                <div>
                  <Sparkles className="mx-auto text-cyan-300" size={42} />
                  <p className="mt-3 font-semibold text-white">Ask for deployment help, upload code, or speak a support question.</p>
                  <p className="mt-1 text-sm text-slate-500">The assistant will answer using your role permissions and live workspace context.</p>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          <div className="mt-4 rounded-lg border border-white/10 bg-white/[0.025] p-3">
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && canSend) chat.mutate();
              }}
              placeholder="Ask: check Vercel deployment, analyze this ZIP, create a support ticket plan, explain server health..."
              className="min-h-24 w-full resize-none rounded-md border border-white/10 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-300/50"
            />
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-slate-200 hover:border-cyan-300/40">
                  <FileUp size={14} /> Upload
                  <input type="file" multiple className="hidden" onChange={(event) => setFiles(Array.from(event.target.files || []))} />
                </label>
                <button type="button" onClick={listening ? stopVoice : startVoice} className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-xs ${listening ? "border-red-300/40 bg-red-400/10 text-red-100" : "border-white/10 bg-white/[0.04] text-slate-200"}`}>
                  {listening ? <MicOff size={14} /> : <Mic size={14} />} {listening ? "Stop" : "Voice"}
                </button>
                <button type="button" onClick={() => setSpeak((value) => !value)} className="inline-flex items-center gap-2 rounded-md border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-slate-200">
                  {speak ? <Volume2 size={14} /> : <VolumeX size={14} />} Speaker
                </button>
                <button type="button" onClick={stopSpeech} className="rounded-md border border-white/10 bg-white/[0.04] px-3 py-2 text-xs text-slate-200">Mute</button>
              </div>
              <button
                type="button"
                disabled={!canSend || chat.isPending}
                onClick={() => chat.mutate()}
                className="inline-flex items-center gap-2 rounded-md bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {chat.isPending ? <Loader2 className="animate-spin" size={16} /> : <Send size={16} />} Send
              </button>
            </div>
            {files.length ? <p className="mt-2 text-xs text-slate-500">{files.map((file) => file.name).join(", ")}</p> : null}
          </div>
        </main>

        <aside className="space-y-4">
          <Panel title="Model Router">
            <select value={provider} onChange={(event) => setProvider(event.target.value)} className="w-full rounded-md border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white">
              {modelOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <p className="mt-2 text-xs text-slate-500">Local mode works now. External model providers can be wired behind this router without changing the UI.</p>
          </Panel>

          <Panel title="Role Controls">
            <div className="space-y-2 text-sm">
              {(currentPolicy.can || []).map((item) => (
                <div key={item} className="flex items-center gap-2 text-slate-300"><ShieldCheck size={14} className="text-emerald-300" /> {item}</div>
              ))}
            </div>
          </Panel>

          <Panel title="Live Events">
            <div className="space-y-2">
              {events.map((event, index) => (
                <div key={`${event.title}-${index}`} className="rounded-md border border-white/10 bg-white/[0.03] p-3">
                  <p className="text-sm font-medium text-white">{event.title}</p>
                  <p className="mt-1 text-xs text-slate-500">{event.detail}</p>
                </div>
              ))}
              {!events.length && <p className="text-xs text-slate-500">Assistant actions and errors appear here.</p>}
            </div>
          </Panel>
        </aside>
      </section>
    </div>
  );
}

function MessageBubble({ message, onSpeak }) {
  const assistant = message.role === "ASSISTANT";
  return (
    <div className={`flex ${assistant ? "justify-start" : "justify-end"}`}>
      <div className={`max-w-[86%] rounded-lg border p-3 text-sm ${assistant ? "border-cyan-300/20 bg-cyan-300/10 text-cyan-50" : "border-white/10 bg-white/[0.05] text-white"}`}>
        <div className="mb-2 flex items-center justify-between gap-3">
          <span className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">{assistant ? "Assistant" : "You"}</span>
          {assistant && <button type="button" onClick={() => onSpeak?.(message.content)} className="text-cyan-200"><Volume2 size={14} /></button>}
        </div>
        <pre className="whitespace-pre-wrap break-words font-sans leading-relaxed">{message.content}</pre>
        {message.attachments?.length ? (
          <div className="mt-3 space-y-1 border-t border-white/10 pt-2 text-xs text-slate-400">
            {message.attachments.map((file) => <p key={file.id}>{file.original_name} · {formatBytes(file.size_bytes)}</p>)}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function Panel({ title, children }) {
  return (
    <section className="rounded-lg border border-white/10 bg-slate-950/60 p-4">
      <h2 className="mb-3 font-semibold text-white">{title}</h2>
      {children}
    </section>
  );
}

function formatBytes(bytes = 0) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
}
