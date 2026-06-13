from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re
import requests

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from apps.core.permissions import Roles, has_role, is_admin_level
from apps.tasks.models import Task


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "your",
    "project",
    "system",
    "platform",
}


class TaskSuggestionService:
    """Local AI-style planner with deterministic heuristics and provider-ready boundary."""

    def generate(self, project, context="", limit=6):
        corpus = " ".join([project.name, project.description, context or ""])
        words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", corpus) if w.lower() not in STOPWORDS]
        top_terms = [word for word, _ in Counter(words).most_common(8)]
        open_statuses = set(project.tasks.exclude(status=Task.Status.DONE).values_list("status", flat=True))

        templates = [
            ("Define acceptance criteria for {term}", "Document measurable acceptance criteria and edge cases for {term}.", "MEDIUM", 2),
            ("Implement secure workflow for {term}", "Build the core workflow, validations, and API contracts related to {term}.", "HIGH", 5),
            ("Add monitoring coverage for {term}", "Track API latency, errors, and user-visible failures around {term}.", "MEDIUM", 3),
            ("Create regression tests for {term}", "Add backend and frontend coverage for critical {term} behavior.", "HIGH", 3),
            ("Prepare client handoff notes for {term}", "Package release notes, file links, and progress summary for client review.", "LOW", 1),
            ("Review deployment readiness for {term}", "Check environment variables, deployment toggle state, rollback notes, and logs.", "CRITICAL", 3),
        ]

        terms = top_terms or ["authentication", "project delivery", "deployment", "analytics"]
        suggestions = []
        for idx, template in enumerate(templates[:limit]):
            term = terms[idx % len(terms)].replace("_", " ")
            title, description, priority, points = template
            confidence = 0.68 + min(0.24, len(top_terms) * 0.02)
            if "BLOCKED" in open_statuses and priority in {"HIGH", "CRITICAL"}:
                confidence += 0.04
            suggestions.append(
                {
                    "title": title.format(term=term.title()),
                    "description": description.format(term=term),
                    "priority": priority,
                    "story_points": points,
                    "confidence": round(min(confidence, 0.96), 2),
                    "rationale": "Generated from project description, open task states, and repeated delivery terms.",
                }
            )
        return suggestions


ROLE_CAPABILITIES = {
    Roles.SUPER_ADMIN: {
        "dashboard": "Global command center",
        "can": ["manage users", "control deployments", "view all projects", "inspect logs", "configure AI models", "manage hosting"],
        "guardrails": ["Never expose secret values; show prefixes/status only."],
    },
    Roles.ADMIN: {
        "dashboard": "Operations command center",
        "can": ["manage assigned projects", "triage tickets", "control deployments", "review hosting health"],
        "guardrails": ["Restrict answers to projects and systems the admin can access."],
    },
    Roles.DEVELOPER: {
        "dashboard": "Developer cockpit",
        "can": ["analyze code", "explain bugs", "suggest fixes", "read assigned project context", "sync git/deployment guidance"],
        "guardrails": ["Do not grant billing, user management, or secret administration actions."],
    },
    Roles.CLIENT: {
        "dashboard": "Client project desk",
        "can": ["ask status questions", "review delivery summaries", "create support requests", "read visible files"],
        "guardrails": ["Use business language; hide internal notes and sensitive implementation details."],
    },
    "TEAM_MEMBER": {
        "dashboard": "Team workspace",
        "can": ["collaborate", "read assigned tasks", "comment on project work"],
        "guardrails": ["Scope output to assigned work."],
    },
    "SUPPORT_STAFF": {
        "dashboard": "Support console",
        "can": ["triage incidents", "draft ticket responses", "summarize customer issues"],
        "guardrails": ["Avoid deployment or billing changes without admin approval."],
    },
    "GUEST_VIEWER": {
        "dashboard": "Read-only viewer",
        "can": ["read public summaries", "ask general questions"],
        "guardrails": ["No sensitive data or write actions."],
    },
}


TEXT_EXTENSIONS = {".txt", ".md", ".json", ".js", ".jsx", ".ts", ".tsx", ".py", ".html", ".css", ".env", ".yml", ".yaml", ".toml", ".ini", ".log"}
PROJECT_MARKERS = {
    "package.json": "Node/Vite/React/Next.js project",
    "requirements.txt": "Python project",
    "manage.py": "Django project",
    "pyproject.toml": "Python package",
    "Dockerfile": "Dockerized service",
    "docker-compose.yml": "Docker Compose stack",
    "vite.config.ts": "Vite frontend",
    "next.config.js": "Next.js app",
}


@dataclass
class AssistantResult:
    answer: str
    intent: str
    actions: list
    context: dict
    provider_used: str = "local"
    fallback_used: bool = False


class EnterpriseAssistantService:
    """Provider-ready assistant engine with deterministic, role-aware behavior."""

    def build_reply(self, user, message, mode="GENERAL", project=None, attachments=None, history=None, requested_provider="auto"):
        text = (message or "").strip()
        role = getattr(user, "role", "GUEST_VIEWER") or "GUEST_VIEWER"
        intent = self.detect_intent(text, mode)
        context = self.system_context(user, project=project)
        attachment_summaries = attachments or []
        actions = self.recommended_actions(intent, role, context, attachment_summaries)
        local_answer = self.compose_answer(
            user=user,
            text=text,
            role=role,
            mode=mode,
            intent=intent,
            context=context,
            actions=actions,
            attachments=attachment_summaries,
            history=history or [],
        )
        routed = self.route_model(text, mode, intent, local_answer, context, attachment_summaries, history or [], requested_provider=requested_provider)
        return AssistantResult(
            answer=routed["answer"],
            intent=intent,
            actions=actions,
            context=context,
            provider_used=routed["provider"],
            fallback_used=routed["fallback"],
        )

    def detect_intent(self, text, mode):
        lowered = text.lower()
        if any(word in lowered for word in ["deploy", "rollback", "build", "vercel", "netlify", "hosting", "ssl", "domain"]):
            return "deployment_hosting"
        if any(word in lowered for word in ["ticket", "issue", "bug", "incident", "support"]):
            return "support_ticket"
        if any(word in lowered for word in ["server", "cpu", "ram", "memory", "disk", "uptime", "monitor"]):
            return "infrastructure"
        if any(word in lowered for word in ["file", "upload", "zip", "analyze", "scan", "code"]):
            return "project_file_analysis"
        if any(word in lowered for word in ["role", "permission", "access", "user"]):
            return "rbac"
        if mode and mode != "GENERAL":
            return mode.lower()
        return "general"

    def provider_status(self):
        return {
            "openai": {
                "enabled": bool(getattr(settings, "OPENAI_API_KEY", "")),
                "model": getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                "best_for": ["coding", "DevOps", "hosting", "debugging", "automation"],
            },
            "gemini": {
                "enabled": bool(getattr(settings, "GEMINI_API_KEY", "")),
                "model": getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash"),
                "best_for": ["long context", "files", "screenshots", "documents", "mixed language"],
            },
            "local": {"enabled": True, "model": "manageai-enterprise-local", "best_for": ["offline fallback", "role policy", "workspace status"]},
        }

    def route_model(self, text, mode, intent, local_answer, context, attachments, history, requested_provider="auto"):
        if requested_provider in {"openai", "gemini", "local"}:
            preferred = requested_provider
        else:
            preferred = self.preferred_provider(intent, attachments)
        fallback = "gemini" if preferred == "openai" else "openai"
        prompt = self.provider_prompt(text, mode, intent, local_answer, context, attachments, history)
        if preferred == "local":
            return {"answer": local_answer, "provider": "local", "fallback": False}
        first = self.call_provider(preferred, prompt)
        if first:
            return {"answer": first, "provider": preferred, "fallback": False}
        second = self.call_provider(fallback, prompt)
        if second:
            return {"answer": second, "provider": fallback, "fallback": True}
        return {"answer": local_answer, "provider": "local", "fallback": bool(preferred != "local")}

    def preferred_provider(self, intent, attachments):
        has_large_or_visual = any(item.get("kind") in {"image", "pdf", "project_archive"} or item.get("size_bytes", 0) > 512 * 1024 for item in attachments or [])
        if has_large_or_visual or intent == "project_file_analysis":
            return "gemini"
        if intent in {"deployment_hosting", "infrastructure", "devops", "automation"}:
            return "openai"
        return getattr(settings, "AI_PROVIDER", "local") if getattr(settings, "AI_PROVIDER", "local") in {"openai", "gemini"} else "openai"

    def provider_prompt(self, text, mode, intent, local_answer, context, attachments, history):
        history_text = "\n".join(f"{item['role']}: {item['content'][:500]}" for item in reversed(history[-6:]))
        attachment_text = "\n".join(f"- {item.get('name')}: {', '.join(item.get('signals') or [])}" for item in attachments[:6])
        return (
            "You are ManageAI, an ultra-advanced enterprise AI workspace assistant. "
            "Understand English, Tamil, and Tamil-English mixed typing naturally. "
            "Answer professionally, be concise first, then give clear production-ready steps. "
            "Never reveal secrets. Respect role-based access and only use the supplied context.\n\n"
            f"Mode: {mode}\nIntent: {intent}\nUser request: {text}\n\n"
            f"Recent chat:\n{history_text or 'None'}\n\n"
            f"Uploaded file signals:\n{attachment_text or 'None'}\n\n"
            f"Workspace context:\n{context}\n\n"
            f"Local analysis baseline:\n{local_answer}\n"
        )

    def call_provider(self, provider, prompt):
        try:
            if provider == "openai":
                return self.call_openai(prompt)
            if provider == "gemini":
                return self.call_gemini(prompt)
        except Exception:
            return ""
        return ""

    def call_openai(self, prompt):
        api_key = getattr(settings, "OPENAI_API_KEY", "")
        if not api_key:
            return ""
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                "input": prompt,
                "temperature": 0.25,
                "max_output_tokens": 1400,
            },
            timeout=45,
        )
        if response.status_code >= 400:
            return ""
        data = response.json()
        if data.get("output_text"):
            return data["output_text"].strip()
        chunks = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("text"):
                    chunks.append(content["text"])
        return "\n".join(chunks).strip()

    def call_gemini(self, prompt):
        api_key = getattr(settings, "GEMINI_API_KEY", "")
        if not api_key:
            return ""
        model = getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash")
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"Content-Type": "application/json", "X-goog-api-key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.25, "maxOutputTokens": 1400}},
            timeout=45,
        )
        if response.status_code >= 400:
            return ""
        data = response.json()
        parts = []
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if part.get("text"):
                    parts.append(part["text"])
        return "\n".join(parts).strip()

    def system_context(self, user, project=None):
        context = {
            "now": timezone.now().isoformat(),
            "role": getattr(user, "role", "GUEST_VIEWER"),
            "capabilities": ROLE_CAPABILITIES.get(getattr(user, "role", ""), ROLE_CAPABILITIES["GUEST_VIEWER"]),
            "projects": {},
            "hosting": {},
            "tickets": {},
            "deployments": {},
            "servers": {},
        }
        try:
            from apps.projects.models import Project

            projects = Project.objects.all()
            if has_role(user, Roles.ADMIN):
                projects = projects.filter(Q(admins=user) | Q(owner=user) | Q(created_by=user)).distinct()
            elif has_role(user, Roles.DEVELOPER):
                projects = projects.filter(Q(developers=user) | Q(teams__members=user)).distinct()
            elif has_role(user, Roles.CLIENT):
                projects = projects.filter(client=user)
            elif not is_admin_level(user):
                projects = projects.none()
            if project:
                projects = projects.filter(pk=project.pk)
            context["projects"] = {"count": projects.count(), "names": list(projects.values_list("name", flat=True)[:8])}
        except Exception as exc:
            context["projects"] = {"error": str(exc)}

        try:
            from apps.hosting.models import DomainStatus, HostedProject, HostingLink

            context["hosting"] = {
                "projects": HostedProject.objects.count() if is_admin_level(user) else 0,
                "down_links": HostingLink.objects.filter(health_status="down").count() if is_admin_level(user) else 0,
                "degraded_links": HostingLink.objects.filter(health_status="degraded").count() if is_admin_level(user) else 0,
                "ssl_warnings": DomainStatus.objects.filter(ssl_status__in=["warning", "critical"]).count() if is_admin_level(user) else 0,
            }
        except Exception as exc:
            context["hosting"] = {"error": str(exc)}

        try:
            from apps.tickets.models import Ticket

            tickets = Ticket.objects.all()
            if has_role(user, Roles.DEVELOPER):
                tickets = tickets.filter(Q(assigned_to=user) | Q(project__developers=user)).distinct()
            elif has_role(user, Roles.CLIENT):
                tickets = tickets.filter(Q(requester=user) | Q(raised_by=user) | Q(project__client=user)).distinct()
            elif not is_admin_level(user):
                tickets = tickets.none()
            context["tickets"] = dict(tickets.values("status").annotate(count=Count("id")).values_list("status", "count"))
        except Exception as exc:
            context["tickets"] = {"error": str(exc)}

        try:
            from apps.deployments.models import DeploymentControl

            deployments = DeploymentControl.objects.all()
            if not is_admin_level(user):
                deployments = deployments.filter(project__developers=user) if has_role(user, Roles.DEVELOPER) else deployments.none()
            context["deployments"] = dict(deployments.values("status").annotate(count=Count("id")).values_list("status", "count"))
        except Exception as exc:
            context["deployments"] = {"error": str(exc)}

        try:
            from apps.server_monitor.models import Server, ServerMetrics

            latest = ServerMetrics.objects.select_related("server").order_by("server_id", "-recorded_at")
            hot = [
                {"server": metric.server.name, "cpu": metric.cpu_percent, "memory": metric.memory_percent, "disk": metric.disk_percent}
                for metric in latest
                if max(metric.cpu_percent, metric.memory_percent, metric.disk_percent) >= 85
            ][:5]
            context["servers"] = {"count": Server.objects.count() if is_admin_level(user) else 0, "hot": hot if is_admin_level(user) else []}
        except Exception as exc:
            context["servers"] = {"error": str(exc)}
        return context

    def analyze_uploaded_file(self, uploaded):
        name = getattr(uploaded, "name", "upload.bin")
        suffix = Path(name).suffix.lower()
        analysis = {
            "name": name,
            "size_bytes": getattr(uploaded, "size", 0),
            "extension": suffix or "none",
            "kind": self.file_kind(name),
            "signals": [],
            "snippet": "",
        }
        marker = PROJECT_MARKERS.get(Path(name).name)
        if marker:
            analysis["signals"].append(marker)
        if suffix in TEXT_EXTENSIONS and getattr(uploaded, "size", 0) <= 512 * 1024:
            pos = uploaded.tell() if hasattr(uploaded, "tell") else 0
            raw = uploaded.read(12000)
            if hasattr(uploaded, "seek"):
                uploaded.seek(pos)
            text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
            analysis["snippet"] = text[:4000]
            analysis["signals"].extend(self.scan_text_signals(text, name))
        if suffix == ".zip":
            analysis["signals"].append("Archive upload detected. Queue project scan before deployment.")
        return analysis

    def file_kind(self, name):
        suffix = Path(name).suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            return "image"
        if suffix == ".pdf":
            return "pdf"
        if suffix == ".zip":
            return "project_archive"
        if suffix in TEXT_EXTENSIONS:
            return "code_or_text"
        return "binary"

    def scan_text_signals(self, text, name):
        lowered = text.lower()
        signals = []
        if "api_key" in lowered or "secret" in lowered or "password" in lowered:
            signals.append("Possible secret/env reference. Verify secrets are not committed.")
        if "todo" in lowered or "fixme" in lowered:
            signals.append("Contains TODO/FIXME markers.")
        if "django" in lowered or "urlpatterns" in lowered:
            signals.append("Django backend code detected.")
        if "react" in lowered or "jsx" in Path(name).suffix.lower():
            signals.append("React frontend code detected.")
        if "docker" in lowered:
            signals.append("Docker/deployment configuration detected.")
        return signals

    def recommended_actions(self, intent, role, context, attachments):
        actions = []
        if intent == "deployment_hosting":
            actions.extend(["Validate environment variables", "Run build/test pipeline", "Check provider logs", "Prepare rollback plan"])
        elif intent == "support_ticket":
            actions.extend(["Classify priority", "Attach logs/screenshots", "Assign owner", "Notify watchers"])
        elif intent == "infrastructure":
            actions.extend(["Check latest metrics", "Inspect high CPU/RAM/disk services", "Create incident ticket if threshold persists"])
        elif intent == "project_file_analysis":
            actions.extend(["Scan uploaded files", "Detect stack and risks", "Generate deployment checklist"])
        else:
            actions.extend(["Clarify goal", "Check accessible project context", "Suggest next best action"])
        if role in {Roles.CLIENT, "GUEST_VIEWER"}:
            actions = [item for item in actions if item not in {"Run build/test pipeline", "Prepare rollback plan"}]
        if attachments:
            actions.insert(0, "Review uploaded file analysis")
        return actions[:6]

    def compose_answer(self, user, text, role, mode, intent, context, actions, attachments, history):
        role_policy = ROLE_CAPABILITIES.get(role, ROLE_CAPABILITIES["GUEST_VIEWER"])
        lines = [
            f"I’m running as your {role_policy['dashboard']} assistant.",
            f"Detected intent: {intent.replace('_', ' ')}.",
        ]
        if text:
            lines.append(f"Request understood: {text[:220]}")
        if attachments:
            lines.append("")
            lines.append("Uploaded file analysis:")
            for item in attachments[:5]:
                signal_text = "; ".join(item.get("signals") or ["No obvious risk markers found"])
                lines.append(f"- {item.get('name')} ({self.human_size(item.get('size_bytes', 0))}, {item.get('kind')}): {signal_text}")
        lines.append("")
        lines.append("Live workspace context:")
        lines.append(f"- Projects visible: {context.get('projects', {}).get('count', 0)}")
        hosting = context.get("hosting", {})
        if hosting and "error" not in hosting:
            lines.append(f"- Hosting: {hosting.get('projects', 0)} projects, {hosting.get('down_links', 0)} down links, {hosting.get('degraded_links', 0)} degraded links, {hosting.get('ssl_warnings', 0)} SSL warnings")
        tickets = context.get("tickets", {})
        if tickets and "error" not in tickets:
            open_count = sum(count for status, count in tickets.items() if status not in {"RESOLVED", "CLOSED"})
            lines.append(f"- Open support workload: {open_count} tickets")
        deployments = context.get("deployments", {})
        if deployments and "error" not in deployments:
            lines.append(f"- Deployment states: {', '.join(f'{key}: {value}' for key, value in deployments.items()) or 'none'}")
        hot = context.get("servers", {}).get("hot", [])
        if hot:
            lines.append(f"- Infrastructure alerts: {len(hot)} hot server metric(s) need attention")
        lines.append("")
        lines.append("Recommended next actions:")
        lines.extend(f"{index + 1}. {action}" for index, action in enumerate(actions))
        lines.append("")
        lines.append("Role guardrail: " + " ".join(role_policy.get("guardrails", [])))
        return "\n".join(lines)

    def human_size(self, value):
        size = float(value or 0)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024 or unit == "GB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024
