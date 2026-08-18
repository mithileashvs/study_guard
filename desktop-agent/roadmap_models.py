"""
Learning Roadmap -- data model.

Plain dataclasses + to_dict/from_dict, same philosophy as
session_context.StudySession: simple, serializable, no ORM. These are
shared by roadmap_generator.py (creates them), roadmap_store.py
(persists/mutates them) and dashboard.py (renders them).

Status values (topic.status):
    LOCKED          -- a prerequisite isn't COMPLETED yet
    NOT_STARTED     -- unlocked, never studied
    IN_PROGRESS     -- has some progress/time logged, not finished
    NEEDS_REVISION  -- was COMPLETED (or attempted) but a quiz/score
                       came back weak; must be revisited
    COMPLETED       -- done
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional

STATUS_LOCKED = "LOCKED"
STATUS_NOT_STARTED = "NOT_STARTED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_NEEDS_REVISION = "NEEDS_REVISION"
STATUS_COMPLETED = "COMPLETED"

# Below this quiz score (%), a topic is flagged NEEDS_REVISION instead
# of being allowed to complete/advance normally. See item 22/24 of the
# spec ("adaptive roadmap" / "needs revision").
REVISION_QUIZ_THRESHOLD = 60


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class StudySessionRecord:
    """One roadmap-topic study session (distinct from main.py's whole
    Study Guard session -- this is scoped to a single topic)."""

    started_at: float
    ended_at: Optional[float] = None
    duration_seconds: float = 0.0

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "StudySessionRecord":
        return StudySessionRecord(
            started_at=d.get("started_at", time.time()),
            ended_at=d.get("ended_at"),
            duration_seconds=d.get("duration_seconds", 0.0),
        )


@dataclass
class QuizResult:
    score_pct: float
    taken_at: float
    strong: bool

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "QuizResult":
        return QuizResult(
            score_pct=d.get("score_pct", 0.0),
            taken_at=d.get("taken_at", time.time()),
            strong=d.get("strong", False),
        )


@dataclass
class Resource:
    title: str
    url: str
    type: str          # tutorial | video | docs | practice | quiz | project
    source: str
    difficulty: str = "any"
    relevance: float = 0.5     # 0..1
    quality: float = 0.5       # 0..1
    last_checked: float = field(default_factory=time.time)

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Resource":
        return Resource(**d)


@dataclass
class Topic:
    id: str
    name: str
    description: str
    order: int
    difficulty: str = "beginner"          # beginner | intermediate | advanced
    estimated_minutes: int = 60
    prerequisites: list = field(default_factory=list)   # list of topic ids

    status: str = STATUS_NOT_STARTED
    progress_pct: float = 0.0
    time_spent_seconds: float = 0.0
    last_studied: Optional[float] = None
    revision_count: int = 0

    sessions: list = field(default_factory=list)          # list[StudySessionRecord]
    resources: dict = field(default_factory=dict)          # {category: [Resource]}
    resources_cached_at: Optional[float] = None
    quiz: list = field(default_factory=list)                # list of question dicts (generated on demand)
    quiz_results: list = field(default_factory=list)        # list[QuizResult]

    def to_dict(self):
        d = asdict(self)
        return d

    @staticmethod
    def from_dict(d: dict) -> "Topic":
        d = dict(d)
        sessions = [StudySessionRecord.from_dict(s) if isinstance(s, dict) else s for s in d.get("sessions", [])]
        resources = {
            cat: [Resource.from_dict(r) if isinstance(r, dict) else r for r in items]
            for cat, items in d.get("resources", {}).items()
        }
        quiz_results = [QuizResult.from_dict(q) if isinstance(q, dict) else q for q in d.get("quiz_results", [])]
        d["sessions"] = sessions
        d["resources"] = resources
        d["quiz_results"] = quiz_results
        known = {f.name for f in Topic.__dataclass_fields__.values()}
        return Topic(**{k: v for k, v in d.items() if k in known})


@dataclass
class Roadmap:
    id: str
    goal: str
    domain: str
    current_level: str
    target_level: str
    deadline_days: int
    daily_minutes: int
    created_at: float
    topics: list = field(default_factory=list)   # list[Topic], ordered

    def to_dict(self):
        return {
            "id": self.id,
            "goal": self.goal,
            "domain": self.domain,
            "current_level": self.current_level,
            "target_level": self.target_level,
            "deadline_days": self.deadline_days,
            "daily_minutes": self.daily_minutes,
            "created_at": self.created_at,
            "topics": [t.to_dict() for t in self.topics],
        }

    @staticmethod
    def from_dict(d: dict) -> "Roadmap":
        topics = [Topic.from_dict(t) for t in d.get("topics", [])]
        return Roadmap(
            id=d["id"],
            goal=d.get("goal", ""),
            domain=d.get("domain", ""),
            current_level=d.get("current_level", "Beginner"),
            target_level=d.get("target_level", ""),
            deadline_days=d.get("deadline_days", 30),
            daily_minutes=d.get("daily_minutes", 60),
            created_at=d.get("created_at", time.time()),
            topics=topics,
        )

    def topic_by_id(self, topic_id: str) -> Optional[Topic]:
        for t in self.topics:
            if t.id == topic_id:
                return t
        return None

    def overall_progress_pct(self) -> float:
        """Real weighted progress from actual topic progress -- never
        a fabricated number. Weighted by estimated_minutes so a 3-hour
        topic counts more than a 20-minute one."""
        total_weight = sum(max(t.estimated_minutes, 1) for t in self.topics) or 1
        earned = sum(max(t.estimated_minutes, 1) * (t.progress_pct / 100.0) for t in self.topics)
        return round(100.0 * earned / total_weight, 1)

    def completed_count(self) -> int:
        return sum(1 for t in self.topics if t.status == STATUS_COMPLETED)

    def remaining_count(self) -> int:
        return sum(1 for t in self.topics if t.status != STATUS_COMPLETED)

    def total_time_spent_seconds(self) -> float:
        return sum(t.time_spent_seconds for t in self.topics)

    def is_mastered(self) -> bool:
        return len(self.topics) > 0 and all(t.status == STATUS_COMPLETED for t in self.topics)
