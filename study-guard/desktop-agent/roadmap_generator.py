"""
Learning Roadmap -- generation.

generate_roadmap(...) turns a free-typed learning goal into an ordered
list of Topic objects. It works for ANY goal, not one hardcoded
subject: a handful of curated curricula cover common goals (so those
come out well-ordered and specific), and anything that doesn't match
one falls back to a generic-but-real scaffold built from the goal text
itself (see _generic_curriculum below) -- never an empty/fake roadmap.

INTEGRATION BOUNDARY -- swapping in a real AI backend
---------------------------------------------------------------------
This mirrors ai_coach.py's documented seam. generate_roadmap() below
is a local, deterministic curriculum engine so the feature is fully
functional with zero external dependencies. To wire in a real LLM:

    def generate_roadmap(goal, current_level, target_level,
                          deadline_days, daily_minutes, existing_topics=None):
        topics_data = call_my_ai_backend(goal, current_level, target_level, ...)
        return _build_topics(topics_data)

Nothing in roadmap_store.py or dashboard.py needs to change -- they
only ever call generate_roadmap(...) and get back Topic objects.
"""

from __future__ import annotations

import time
from typing import Optional

from roadmap_models import Topic, STATUS_NOT_STARTED, STATUS_COMPLETED, _new_id

# ----------------------------------------------------------------------
# Curated curricula for common goals. Each entry is a list of
# (name, description, difficulty, estimated_minutes, prereq_index_offsets)
# prereq_index_offsets: list of indices (into this same list) that must
# come before this topic. Kept small/readable -- these are seeds, not
# an attempt to be exhaustive.
# ----------------------------------------------------------------------
_CURRICULA = {
    "python": [
        ("Python Basics", "Syntax, variables, data types, and running your first scripts.", "beginner", 90, []),
        ("Control Flow", "if/else, loops, and writing conditional logic.", "beginner", 90, [0]),
        ("Functions", "Defining reusable functions, arguments, and return values.", "beginner", 90, [1]),
        ("Data Structures", "Lists, dicts, sets, tuples and when to use each.", "beginner", 120, [2]),
        ("Object-Oriented Python", "Classes, objects, inheritance, and encapsulation.", "intermediate", 150, [3]),
        ("Modules & Packages", "Organizing code, imports, and virtual environments.", "intermediate", 90, [4]),
        ("File I/O & Error Handling", "Reading/writing files and try/except patterns.", "intermediate", 90, [4]),
        ("Testing & Debugging", "Writing tests and debugging real programs.", "intermediate", 90, [6]),
        ("Python Projects", "Build 1-2 complete small applications end-to-end.", "advanced", 240, [5, 7]),
    ],
    "machine learning": [
        ("Python for ML", "Python fundamentals needed before ML tooling.", "beginner", 120, []),
        ("NumPy", "Arrays, vectorization, and numerical computing.", "beginner", 90, [0]),
        ("Pandas", "DataFrames, cleaning, and exploring datasets.", "beginner", 120, [1]),
        ("Mathematics for ML", "Linear algebra and calculus intuition for ML.", "beginner", 150, [0]),
        ("Statistics & Probability", "Distributions, hypothesis testing, and inference.", "beginner", 150, [3]),
        ("Data Visualization", "Communicating data with matplotlib/seaborn-style plots.", "intermediate", 90, [2]),
        ("Regression", "Linear/logistic regression and evaluation metrics.", "intermediate", 120, [4, 5]),
        ("Classification", "Classic classifiers and choosing the right one.", "intermediate", 120, [6]),
        ("Decision Trees & Ensembles", "Trees, random forests, boosting.", "intermediate", 120, [7]),
        ("Clustering", "Unsupervised learning: k-means and friends.", "intermediate", 90, [6]),
        ("Neural Networks", "Perceptrons, backprop, and simple deep learning.", "advanced", 180, [8]),
        ("Model Evaluation", "Cross-validation, overfitting, metrics that matter.", "advanced", 90, [8, 10]),
        ("ML Projects", "End-to-end project: data to deployed model.", "advanced", 240, [11, 9]),
    ],
    "web development": [
        ("HTML Fundamentals", "Semantic markup and page structure.", "beginner", 60, []),
        ("CSS Fundamentals", "Styling, layout, flexbox and grid.", "beginner", 90, [0]),
        ("JavaScript Basics", "Variables, functions, DOM manipulation.", "beginner", 120, [1]),
        ("Responsive Design", "Building layouts that work on any screen size.", "intermediate", 90, [1]),
        ("Modern JavaScript", "ES6+, async/await, fetch, modules.", "intermediate", 120, [2]),
        ("Frontend Framework", "Component-based UI (e.g. React) fundamentals.", "intermediate", 180, [4]),
        ("Backend Fundamentals", "Servers, routing, and REST APIs.", "intermediate", 150, [2]),
        ("Databases", "Relational/NoSQL basics and connecting to an app.", "intermediate", 120, [6]),
        ("Authentication & Deployment", "Auth basics and shipping an app live.", "advanced", 120, [5, 7]),
        ("Full-Stack Project", "Build and deploy a complete full-stack app.", "advanced", 240, [8]),
    ],
    "data structures and algorithms": [
        ("Complexity Analysis", "Big-O, time/space tradeoffs.", "beginner", 60, []),
        ("Arrays & Strings", "Core operations and common patterns.", "beginner", 90, [0]),
        ("Linked Lists", "Singly/doubly linked lists and pointer manipulation.", "beginner", 90, [1]),
        ("Stacks & Queues", "LIFO/FIFO structures and their use cases.", "beginner", 60, [1]),
        ("Recursion", "Thinking recursively and base-case design.", "intermediate", 90, [1]),
        ("Trees", "Binary trees, BSTs, traversals.", "intermediate", 120, [4]),
        ("Heaps & Priority Queues", "Heap operations and use cases.", "intermediate", 90, [5]),
        ("Hashing", "Hash maps/sets and collision handling.", "intermediate", 90, [1]),
        ("Graphs", "Representations, BFS/DFS, shortest paths.", "advanced", 150, [5, 7]),
        ("Dynamic Programming", "Memoization, tabulation, classic DP problems.", "advanced", 180, [4, 8]),
        ("Practice & Mock Interviews", "Timed problem sets across all topics above.", "advanced", 240, [9]),
    ],
    "java": [
        ("Java Basics", "Syntax, variables, types, control flow.", "beginner", 90, []),
        ("OOP in Java", "Classes, inheritance, interfaces, polymorphism.", "beginner", 120, [0]),
        ("Collections", "List/Set/Map, generics, and when to use each.", "intermediate", 120, [1]),
        ("Exception Handling", "Checked/unchecked exceptions and try-with-resources.", "intermediate", 60, [1]),
        ("Streams & Lambdas", "Functional-style Java, streams API.", "intermediate", 90, [2]),
        ("Concurrency Basics", "Threads, synchronization fundamentals.", "advanced", 120, [2]),
        ("Build Tools & Testing", "Maven/Gradle basics and unit testing.", "intermediate", 90, [3]),
        ("Java Projects", "Build a complete small Java application.", "advanced", 240, [4, 5, 6]),
    ],
}

# Aliases so close phrasing still hits a curated curriculum.
_ALIASES = {
    "ml": "machine learning",
    "ai": "machine learning",
    "artificial intelligence": "machine learning",
    "dsa": "data structures and algorithms",
    "data structures": "data structures and algorithms",
    "algorithms": "data structures and algorithms",
    "web dev": "web development",
    "webdev": "web development",
    "frontend": "web development",
    "full stack": "web development",
    "fullstack": "web development",
}


def _match_curriculum(goal: str) -> Optional[list]:
    g = goal.strip().lower()
    if g in _ALIASES:
        g = _ALIASES[g]
    if g in _CURRICULA:
        return _CURRICULA[g]
    for key in _CURRICULA:
        if key in g or g in key:
            return _CURRICULA[key]
    for alias, key in _ALIASES.items():
        if alias in g:
            return _CURRICULA[key]
    return None


def _generic_curriculum(goal: str) -> list:
    """Fallback scaffold for any goal without a curated curriculum.
    Real, ordered, goal-specific stages -- not a placeholder. Works
    for arbitrary domains (languages, sciences, exam prep, etc.)."""
    g = goal.strip() or "your goal"
    return [
        (f"{g}: Fundamentals", f"Core vocabulary, tools, and building blocks of {g}.", "beginner", 90, []),
        (f"{g}: Core Concepts", f"The essential ideas and techniques underpinning {g}.", "beginner", 120, [0]),
        (f"{g}: Guided Practice", f"Applying {g} concepts to structured exercises.", "intermediate", 120, [1]),
        (f"{g}: Intermediate Topics", f"Deeper, less common but important parts of {g}.", "intermediate", 150, [2]),
        (f"{g}: Real-World Application", f"Using {g} in realistic, less-guided scenarios.", "advanced", 150, [3]),
        (f"{g}: Advanced Topics", f"Edge cases and advanced techniques in {g}.", "advanced", 150, [4]),
        (f"{g}: Capstone Project", f"Build something real that demonstrates {g} mastery.", "advanced", 240, [5]),
    ]


def generate_roadmap(
    goal: str,
    current_level: str = "Beginner",
    target_level: str = "",
    deadline_days: int = 30,
    daily_minutes: int = 60,
    already_completed: Optional[list] = None,
) -> list:
    """Returns a list of Topic objects for `goal`, ordered, with
    prerequisites wired up by id. `already_completed` is a list of
    topic names (case-insensitive) the user says they already know --
    those are seeded in as COMPLETED instead of NOT_STARTED, per spec
    item 14 ("topics already completed")."""
    already_completed = {n.strip().lower() for n in (already_completed or [])}

    curriculum = _match_curriculum(goal) or _generic_curriculum(goal)

    topics: list[Topic] = []
    ids_by_index = [_new_id() for _ in curriculum]

    for i, (name, desc, difficulty, minutes, prereq_idxs) in enumerate(curriculum):
        status = STATUS_COMPLETED if name.strip().lower() in already_completed else STATUS_NOT_STARTED
        topic = Topic(
            id=ids_by_index[i],
            name=name,
            description=desc,
            order=i,
            difficulty=difficulty,
            estimated_minutes=minutes,
            prerequisites=[ids_by_index[j] for j in prereq_idxs],
            status=status,
            progress_pct=100.0 if status == STATUS_COMPLETED else 0.0,
        )
        topics.append(topic)

    return topics
