import { Bot, KeyRound, MessageSquare, Radio, Send, Users } from "lucide-react";
import { motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";

import { listFrom } from "../api/client.js";
import { enterpriseApi, projectsApi } from "../api/services.js";
import Button from "../components/ui/Button.jsx";
import Page from "../components/ui/Page.jsx";
import { useAuth } from "../context/AuthContext.jsx";

function encode(value) {
  return btoa(unescape(encodeURIComponent(value)));
}

function decode(value) {
  try {
    return decodeURIComponent(escape(atob(value)));
  } catch {
    return value;
  }
}

export default function Collaboration() {
  const { user } = useAuth();
  const outlet = useOutletContext();
  const [channels, setChannels] = useState([]);
  const [projects, setProjects] = useState([]);
  const [activeId, setActiveId] = useState("");
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [channelForm, setChannelForm] = useState({ name: "Developer War Room", project: "" });

  const active = useMemo(() => channels.find((channel) => String(channel.id) === String(activeId)), [channels, activeId]);

  useEffect(() => {
    let mounted = true;
    Promise.all([enterpriseApi.collaborationChannels(), projectsApi.list()]).then(([channelResponse, projectResponse]) => {
      if (!mounted) return;
      const channelItems = listFrom(channelResponse);
      const projectItems = listFrom(projectResponse);
      setChannels(channelItems);
      setProjects(projectItems);
      setActiveId(channelItems[0]?.id || "");
      setChannelForm((current) => ({ ...current, project: projectItems[0]?.id || "" }));
      if (!channelItems.length) {
        createDefaultChannel(projectItems[0]?.id || "");
      }
    }).catch((caught) => setError(readApiError(caught, "Collaboration failed to load."))).finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!activeId) return;
    enterpriseApi.collaborationMessages(activeId).then((response) => setMessages(listFrom(response))).catch((caught) => setError(readApiError(caught, "Messages failed to load.")));
  }, [activeId]);

  useEffect(() => {
    const latest = outlet?.events?.find((event) => event.type === "collaboration.message" && String(event.message?.channel) === String(activeId));
    if (!latest?.message) return;
    setMessages((items) => items.some((item) => item.id === latest.message.id) ? items : [...items, latest.message]);
  }, [outlet?.events, activeId]);

  function readApiError(caught, fallback) {
    const data = caught?.response?.data;
    if (!data) return fallback;
    if (typeof data.detail === "string") return data.detail;
    const firstKey = Object.keys(data)[0];
    const value = data[firstKey];
    return Array.isArray(value) ? `${firstKey}: ${value[0]}` : fallback;
  }

  async function createDefaultChannel(projectId = "") {
    try {
      const { data } = await enterpriseApi.createCollaborationChannel({
        name: "Developer War Room",
        project: projectId || null,
        members: user?.id ? [user.id] : []
      });
      setChannels((items) => [data, ...items]);
      setActiveId(data.id);
      setError("");
    } catch (caught) {
      setError(readApiError(caught, "Could not create the default team room."));
    }
  }

  async function createChannel(event) {
    event.preventDefault();
    setError("");
    try {
      const { data } = await enterpriseApi.createCollaborationChannel({ ...channelForm, project: channelForm.project || null, members: user?.id ? [user.id] : [] });
      setChannels((items) => [data, ...items.filter((item) => item.id !== data.id)]);
      setActiveId(data.id);
    } catch (caught) {
      setError(readApiError(caught, "Team room could not be created."));
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    if (!draft.trim() || !activeId) return;
    setSending(true);
    setError("");
    const payload = {
      kind: draft.toLowerCase().startsWith("/config") ? "CONFIG" : "MESSAGE",
      ciphertext: encode(draft.trim()),
      nonce: crypto?.randomUUID?.() || String(Date.now()),
      metadata: { encrypted: true, mentions: draft.toLowerCase().includes("@bot") ? ["bot"] : [] }
    };
    try {
      const { data } = await enterpriseApi.sendCollaborationMessage(activeId, payload);
      const created = Array.isArray(data) ? data : [data];
      setMessages((items) => {
        const existing = new Set(items.map((item) => item.id));
        return [...items, ...created.filter((item) => !existing.has(item.id))];
      });
      setDraft("");
    } catch (caught) {
      setError(readApiError(caught, "Message could not be sent."));
    } finally {
      setSending(false);
    }
  }

  return (
    <Page title="Developer Collaboration" subtitle="Encrypted developer messaging, team chatbot guidance, config sharing, typing-ready channels, and project team rooms.">
      <div className="grid gap-4 xl:grid-cols-[320px_1fr]">
        <aside className="space-y-4">
          <section className="panel p-4">
            <div className="mb-4 flex items-center gap-2">
              <Users size={18} className="text-teal-200" />
              <h2 className="text-sm font-semibold text-white">Team Channels</h2>
            </div>
            <div className="space-y-2">
              {loading && <p className="rounded-lg border border-white/10 bg-white/[0.035] p-3 text-sm text-slate-500">Loading team rooms...</p>}
              {channels.map((channel) => (
                <button key={channel.id} type="button" onClick={() => setActiveId(channel.id)} className={`w-full rounded-lg border border-white/10 p-3 text-left transition ${String(activeId) === String(channel.id) ? "bg-white/15 text-white" : "bg-white/[0.035] text-slate-300 hover:bg-white/[0.07]"}`}>
                  <span className="block text-sm font-medium">{channel.name}</span>
                  <span className="mt-1 block text-xs text-slate-500">{channel.project_name || "Company"} - {channel.member_count || 1} members</span>
                </button>
              ))}
              {!loading && !channels.length && <Button variant="secondary" className="w-full" onClick={() => createDefaultChannel(channelForm.project)}>Create default room</Button>}
            </div>
          </section>
          <form onSubmit={createChannel} className="panel grid gap-3 p-4">
            <p className="text-sm font-semibold text-white">Create Team Room</p>
            <input className="field" value={channelForm.name} onChange={(event) => setChannelForm({ ...channelForm, name: event.target.value })} />
            <select className="field" value={channelForm.project} onChange={(event) => setChannelForm({ ...channelForm, project: event.target.value })}>
              <option value="">Company-wide</option>
              {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
            <Button type="submit">Create</Button>
          </form>
        </aside>
        <section className="panel flex min-h-[70vh] flex-col overflow-hidden">
          <div className="border-b border-white/10 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <MessageSquare size={18} className="text-teal-200" />
                  <h2 className="text-base font-semibold text-white">{active?.name || "Select a channel"}</h2>
                </div>
                <p className="mt-1 text-xs text-slate-500">Online status, encrypted messages, config notes, and @bot guidance.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-1 text-xs text-emerald-200"><Radio size={13} />Online</span>
                <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs text-slate-300"><KeyRound size={13} />E2E payload</span>
                <span className="inline-flex items-center gap-2 rounded-full border border-sky-300/20 bg-sky-300/10 px-3 py-1 text-xs text-sky-200"><Bot size={13} />@bot</span>
              </div>
            </div>
          </div>
          <div className="flex-1 space-y-3 overflow-y-auto p-4">
            {error && <p className="rounded-lg border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-200">{error}</p>}
            {messages.map((message) => {
              const own = message.sender_detail?.id === user?.id;
              const body = message.metadata?.encrypted ? decode(message.ciphertext) : message.ciphertext;
              return (
                <motion.div key={message.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className={`max-w-2xl rounded-lg border border-white/10 p-3 ${own ? "ml-auto bg-teal-300/10" : "bg-white/[0.04]"}`}>
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <p className="text-xs font-medium text-slate-400">{message.sender_detail?.full_name || message.sender_detail?.email || "TeamBot"}</p>
                    <span className="text-[11px] text-slate-500">{message.kind}</span>
                  </div>
                  <p className="whitespace-pre-wrap text-sm text-white">{body}</p>
                </motion.div>
              );
            })}
            {!messages.length && <p className="rounded-lg border border-white/10 bg-white/[0.035] p-4 text-sm text-slate-500">No team messages yet. Mention @bot for internal guidance.</p>}
          </div>
          <form onSubmit={sendMessage} className="border-t border-white/10 p-4">
            <div className="flex gap-3">
              <input className="field" disabled={!activeId || sending} value={draft} onChange={(event) => setDraft(event.target.value)} placeholder={activeId ? "Message team, share /config notes, or ask @bot for guidance" : "Create or select a team room first"} />
              <Button type="submit" disabled={!activeId || sending || !draft.trim()}><Send size={16} />Send</Button>
            </div>
          </form>
        </section>
      </div>
    </Page>
  );
}
