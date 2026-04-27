from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import date, timedelta

from logger_config import setup_logger

logger = setup_logger("pawpal_system")


@dataclass
class Task:
    """Represents a single pet care activity."""
    id: int
    name: str
    starting_time: str
    category: str = "general"
    duration_minutes: int = 0
    priority: int = 0
    recurrence: Optional[str] = None
    last_done: Optional[date] = None
    notes: Optional[str] = None
    completed: bool = False

    def is_due(self) -> bool:
        """Return True when the task should be scheduled today."""
        if self.last_done is None:
            return True
        if self.recurrence == "daily":
            return self.last_done < date.today()
        if self.recurrence == "weekly":
            return (date.today() - self.last_done) >= timedelta(days=7)
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the task to a plain dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "starting_time": self.starting_time,
            "category": self.category,
            "duration_minutes": self.duration_minutes,
            "priority": self.priority,
            "recurrence": self.recurrence,
            "last_done": self.last_done,
            "notes": self.notes,
        }

    def mark_complete(self, done_date: Optional[date] = None) -> None:
        """Mark the task completed and record the completion date."""
        self.completed = True
        self.last_done = done_date or date.today()


@dataclass
class ScheduledItem:
    task: Task
    start_minute: Optional[int] = None
    end_minute: Optional[int] = None


class Pet:
    """Represents a pet and its collection of care tasks."""

    def __init__(
        self,
        id: int,
        name: str,
        species: str,
        age_years: float,
        preferences: Optional[List] = None,
        tasks: Optional[List[Task]] = None,
    ) -> None:
        self.id = id
        self.name = name
        self.species = species
        self.age_years = age_years
        self.preferences = preferences if preferences is not None else []
        self.tasks = tasks if tasks is not None else []

    def get_task(self, task_id: int) -> Optional[Task]:
        """Return the task with *task_id*, or None if not found."""
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None

    def add_task(self, task: Task) -> None:
        """Add *task* to this pet (raises ValueError on duplicate id)."""
        if task is None:
            logger.warning("Attempted to add None as a task to pet '%s'", self.name)
            return
        if self.get_task(task.id) is not None:
            raise ValueError(f"Task with id {task.id} already exists for pet '{self.name}'")
        self.tasks.append(task)
        logger.debug("Added task '%s' (id=%d) to pet '%s'", task.name, task.id, self.name)

    def edit_task(self, task_id: int, updates: Dict[str, Any]) -> None:
        """Apply *updates* to the task identified by *task_id*."""
        t = self.get_task(task_id)
        if t is None:
            raise KeyError(f"Task {task_id} not found for pet '{self.name}'")
        for k, v in updates.items():
            if hasattr(t, k):
                setattr(t, k, v)
        logger.debug("Edited task id=%d on pet '%s': %s", task_id, self.name, updates)

    def remove_task(self, task_id: int) -> None:
        """Remove the task identified by *task_id* (raises KeyError if missing)."""
        t = self.get_task(task_id)
        if t is None:
            raise KeyError(f"Task {task_id} not found for pet '{self.name}'")
        self.tasks.remove(t)
        logger.debug("Removed task id=%d from pet '%s'", task_id, self.name)

    def list_tasks(self) -> List[Task]:
        """Return a shallow copy of this pet's task list."""
        return list(self.tasks)


class Scheduler:
    """
    Deterministic greedy scheduler.

    Filters due tasks → scores each task once (cached) → sorts by score desc
    then id → assigns cumulative minute-based time slots until time runs out.
    """

    def __init__(
        self,
        pet: Optional[Pet] = None,
        user_prefs: Optional[Dict] = None,
        constraints: Optional[Dict] = None,
    ) -> None:
        self.pet = pet
        self.user_prefs = user_prefs or {}
        self.constraints = constraints or {}
        self.algorithm_params: Dict[str, Any] = {}
        self._score_cache: Dict[int, float] = {}

    def score_task(self, task: Task) -> float:
        """Compute a deterministic priority score for a task (higher is better)."""
        if task.id in self._score_cache:
            return self._score_cache[task.id]
        score = float(task.priority) * 10.0 - (task.duration_minutes / 10.0)
        self._score_cache[task.id] = score
        return score

    def sort_by_time(self, tasks: Optional[List[Task]] = None) -> List[Task]:
        """Return *tasks* sorted by their ``starting_time`` (HH:MM string)."""
        if tasks is None:
            if not self.pet:
                return []
            tasks = list(self.pet.tasks)

        def _to_minutes(t: Task) -> int:
            st = t.starting_time or ""
            try:
                h, m = st.split(":")
                return int(h) * 60 + int(m)
            except Exception:
                return 24 * 60

        return sorted(tasks, key=_to_minutes)

    def mark_task_complete(
        self, task_id: int, done_date: Optional[date] = None
    ) -> Optional[Task]:
        """
        Mark a task complete and auto-create the next recurrence if applicable.

        Returns the new Task when a recurrence is created, otherwise None.
        """
        if not self.pet:
            raise KeyError("Scheduler has no pet assigned")
        t = self.pet.get_task(task_id)
        if t is None:
            raise KeyError(f"Task {task_id} not found for pet '{self.pet.name}'")

        t.mark_complete(done_date)
        logger.info("Marked task '%s' complete for pet '%s'", t.name, self.pet.name)

        if t.recurrence in ("daily", "weekly"):
            existing_ids = [x.id for x in self.pet.tasks]
            new_id = (max(existing_ids) + 1) if existing_ids else (t.id + 1)
            new_task = Task(
                new_id,
                t.name,
                t.starting_time,
                t.category,
                t.duration_minutes,
                t.priority,
                t.recurrence,
                None,
                t.notes,
                False,
            )
            new_task.last_done = date.today()
            self.pet.add_task(new_task)
            logger.info(
                "Created next recurrence for '%s' (id=%d, recurrence=%s)",
                new_task.name, new_task.id, new_task.recurrence,
            )
            return new_task
        return None

    def prioritize_tasks(self) -> List[Task]:
        """Return due tasks sorted by score (descending) then id (for determinism)."""
        if not self.pet:
            return []
        scored = [(self.score_task(t), t) for t in self.pet.tasks if t.is_due()]
        scored.sort(key=lambda si: (-si[0], si[1].id))
        return [t for _, t in scored]

    def generate_schedule(self, time_available_minutes: int) -> List[ScheduledItem]:
        """
        Greedy scheduler: pick the highest-scoring due tasks until the available
        time is exhausted.
        """
        schedule: List[ScheduledItem] = []
        remaining = time_available_minutes
        cursor = 0
        for task in self.prioritize_tasks():
            if task.duration_minutes <= 0:
                continue
            if task.duration_minutes <= remaining:
                si = ScheduledItem(
                    task=task,
                    start_minute=cursor,
                    end_minute=cursor + task.duration_minutes,
                )
                schedule.append(si)
                cursor += task.duration_minutes
                remaining -= task.duration_minutes
            if remaining <= 0:
                break
        logger.info(
            "Generated schedule: %d items in %d min (of %d available)",
            len(schedule),
            cursor,
            time_available_minutes,
        )
        return schedule

    def explain_reasoning(self, schedule: List[ScheduledItem]) -> str:
        """Return a concise rule-based explanation of why each task was scheduled."""
        lines = [
            f"Selected {si.task.name} (priority={si.task.priority}, "
            f"duration={si.task.duration_minutes} min)"
            for si in schedule
        ]
        if not lines:
            return "No tasks could be scheduled within the available time."
        return "; ".join(lines)

    def same_schedule(
        self, schedule_one: ScheduledItem, schedule_two: ScheduledItem
    ) -> bool:
        """
        Return True when two scheduled items do NOT overlap.

        Returns False (and logs a warning) when their [start, end) intervals
        overlap.  Items with missing time values are treated as non-conflicting.
        """
        a_start, a_end = schedule_one.start_minute, schedule_one.end_minute
        b_start, b_end = schedule_two.start_minute, schedule_two.end_minute
        if None in (a_start, a_end, b_start, b_end):
            return True
        if a_end <= b_start or b_end <= a_start:
            return True
        logger.warning(
            "Time conflict detected between '%s' and '%s'",
            schedule_one.task.name,
            schedule_two.task.name,
        )
        return False

    def detect_time_conflicts(
        self, pets: List[Pet], time_available: int = 0
    ) -> str:
        """
        Check whether the total time required across all pets' due tasks
        exceeds *time_available*.

        Returns a human-readable summary string.
        """
        summaries: List[str] = []
        total = 0
        for p in pets:
            s = Scheduler(pet=p, user_prefs=self.user_prefs)
            pet_minutes = sum(
                t.duration_minutes for t in s.prioritize_tasks() if t.duration_minutes > 0
            )
            total += pet_minutes
            summaries.append(f"{p.name}: {pet_minutes} min")

        detail = " | ".join(summaries) if summaries else "no pets"
        if time_available and total > time_available:
            msg = (
                f"⚠ Time overloaded: {detail} | "
                f"Total {total} min needed but only {time_available} min available"
            )
            logger.warning(msg)
            return msg

        msg = f"✓ No conflicts: {detail} | Total {total} min fits in {time_available} min"
        logger.info(msg)
        return msg


class User:
    """Represents the pet owner who triggers scheduling."""

    def __init__(
        self,
        name: str,
        owner_preferences: Optional[Dict] = None,
        time_available_minutes: int = 0,
    ) -> None:
        self.name = name
        self.owner_preferences = owner_preferences or {}
        self.time_available_minutes = time_available_minutes
        self.pets: List[Pet] = []

    def get_pet(self, pet_id: int) -> Optional[Pet]:
        """Return the pet with *pet_id*, or None."""
        return next((p for p in self.pets if p.id == pet_id), None)

    def enter_info(self, **info) -> None:
        """Update owner attributes from keyword arguments."""
        for k, v in info.items():
            setattr(self, k, v)

    def add_pet(self, pet: Pet) -> None:
        """Add *pet* to the owner's collection (raises ValueError on duplicate)."""
        if self.get_pet(pet.id) is not None:
            raise ValueError(f"Pet with id {pet.id} already exists")
        self.pets.append(pet)
        logger.info("Added pet '%s' (id=%d, species=%s)", pet.name, pet.id, pet.species)

    def edit_pet(self, pet_id: int, updates: Dict[str, Any]) -> None:
        """Apply *updates* to the pet identified by *pet_id*."""
        p = self.get_pet(pet_id)
        if p is None:
            raise KeyError(f"Pet {pet_id} not found")
        for k, v in updates.items():
            if hasattr(p, k):
                setattr(p, k, v)

    def remove_pet(self, pet_id: int) -> None:
        """Remove the pet identified by *pet_id*."""
        p = self.get_pet(pet_id)
        if p is None:
            raise KeyError(f"Pet {pet_id} not found")
        self.pets.remove(p)
        logger.info("Removed pet id=%d", pet_id)

    def generate_schedule_for_pet(self, pet_id: int) -> List[ScheduledItem]:
        """Generate a daily schedule for the given pet using this owner's time budget."""
        p = self.get_pet(pet_id)
        if p is None:
            raise KeyError(f"Pet {pet_id} not found")
        gen = Scheduler(pet=p, user_prefs=self.owner_preferences)
        return gen.generate_schedule(self.time_available_minutes)

    def filter_tasks(
        self,
        completed: Optional[bool] = None,
        pet_name: Optional[str] = None,
    ) -> List[Task]:
        """
        Return tasks across all pets, optionally filtered by completion status
        and/or pet name (case-insensitive).
        """
        result: List[Task] = []
        for p in self.pets:
            if pet_name is not None and p.name.lower() != pet_name.lower():
                continue
            for t in p.tasks:
                if completed is None or t.completed == completed:
                    result.append(t)
        return result
