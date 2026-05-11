from collections import Counter
import re

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
