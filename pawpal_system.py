from dataclasses import dataclass, field
from datetime import date, timedelta


# ── Helpers ───────────────────────────────────────────────────────────────────

def _time_to_minutes(time_str: str) -> int:
    """Convert 'HH:MM' string to minutes since midnight."""
    h, m = time_str.split(":")
    return int(h) * 60 + int(m)


def _minutes_to_time(minutes: int) -> str:
    """Convert minutes since midnight to 'HH:MM' string."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# ── Task ──────────────────────────────────────────────────────────────────────

@dataclass
class Task:
    name: str
    category: str          # "walk", "feeding", "meds", "grooming"
    duration_minutes: int
    priority: str          # "low", "medium", "high"
    status: str = "pending"  # "pending" or "complete"

    # Recurring task fields
    recurrence: str | None = None          # None (one-time), "daily", "weekly"
    recurrence_days: list[int] = field(default_factory=list)  # 0=Mon..6=Sun, used when recurrence="weekly"

    # Preferred start time for conflict detection
    preferred_time: str | None = None      # "HH:MM", e.g. "08:00"

    # Computed due date — set automatically by next_occurrence()
    due_date: date | None = None           # None means "due today / use recurrence logic"

    def mark_complete(self) -> None:
        """Mark this task as complete."""
        self.status = "complete"

    def next_occurrence(self) -> "Task":
        """
        Return a new pending Task for the next occurrence of this recurring task.
        Raises ValueError for one-time tasks (recurrence=None).

        timedelta arithmetic:
          - daily  → due_date = today + timedelta(days=1)
          - weekly → due_date = the nearest future date whose weekday is in
                     recurrence_days, found by stepping forward one day at a
                     time with timedelta(days=offset) until a match is found.
        """
        if self.recurrence is None:
            raise ValueError(f"'{self.name}' is a one-time task and has no next occurrence.")

        today = date.today()

        if self.recurrence == "daily":
            next_due = today + timedelta(days=1)
        elif self.recurrence == "weekly":
            # Step forward day-by-day (1..7) until we land on a matching weekday
            next_due = next(
                today + timedelta(days=offset)
                for offset in range(1, 8)
                if (today + timedelta(days=offset)).weekday() in self.recurrence_days
            )
        else:
            next_due = today + timedelta(days=1)   # safe fallback

        return Task(
            name=self.name,
            category=self.category,
            duration_minutes=self.duration_minutes,
            priority=self.priority,
            status="pending",
            recurrence=self.recurrence,
            recurrence_days=list(self.recurrence_days),  # copy so lists don't share state
            preferred_time=self.preferred_time,
            due_date=next_due,
        )

    def is_due_today(self) -> bool:
        """
        Return True if this task should be included in today's schedule.

        If due_date is set (spawned by next_occurrence), the task is due when
        that date has arrived.  Without a due_date, fall back to the original
        recurrence-day logic so manually created tasks still work.
        """
        today = date.today()
        if self.due_date is not None:
            return self.due_date <= today
        if self.recurrence is None or self.recurrence == "daily":
            return True
        if self.recurrence == "weekly":
            return today.weekday() in self.recurrence_days
        return True


# ── Pet ───────────────────────────────────────────────────────────────────────

@dataclass
class Pet:
    name: str
    breed: str
    age: int
    sex: str
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a task to this pet's task list."""
        self.tasks.append(task)

    def remove_task(self, task_name: str) -> None:
        """Remove a task from this pet's task list by name."""
        self.tasks = [t for t in self.tasks if t.name != task_name]

    def mark_task_complete(self, task_name: str) -> "Task | None":
        """
        Mark the named task complete.

        If the task recurs (daily or weekly), automatically appends a fresh
        pending copy to this pet's task list for the next occurrence and
        returns it.  Returns None for one-time tasks.

        Raises ValueError if no task with that name exists.
        """
        for task in self.tasks:
            if task.name == task_name:
                task.mark_complete()
                if task.recurrence is not None:
                    next_task = task.next_occurrence()
                    self.tasks.append(next_task)
                    return next_task
                return None
        raise ValueError(f"No task named '{task_name}' found for {self.name}.")


# ── Owner ─────────────────────────────────────────────────────────────────────

@dataclass
class Owner:
    name: str
    available_time_minutes: int
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner's pet list."""
        self.pets.append(pet)

    def remove_pet(self, pet_name: str) -> None:
        """Remove a pet from this owner's pet list by name."""
        self.pets = [p for p in self.pets if p.name != pet_name]

    def get_all_tasks(self) -> list[Task]:
        """Return a flat list of all tasks across all pets."""
        all_tasks = []
        for pet in self.pets:
            all_tasks.extend(pet.tasks)
        return all_tasks

    def filter_tasks(
        self,
        pet_name: str | None = None,
        status: str | None = None,
    ) -> list[Task]:
        """
        Return tasks filtered by pet name and/or status.

        Both parameters are optional and can be combined. Omitting a parameter
        means "do not filter on this dimension". The method iterates all pets
        and skips non-matching ones early (before checking individual tasks),
        so filtering by pet_name avoids scanning irrelevant task lists.

        Args:
            pet_name: If given, only include tasks belonging to the pet with
                      this exact name. Case-sensitive. Pass None to include
                      tasks from all pets.
            status:   If given, only include tasks whose status matches this
                      string ("pending" or "complete"). Pass None to include
                      tasks of any status.

        Returns:
            A new list of Task objects that satisfy all supplied filters,
            preserving the original per-pet insertion order. Returns an empty
            list if no tasks match.
        """
        results = []
        for pet in self.pets:
            if pet_name is not None and pet.name != pet_name:
                continue
            for task in pet.tasks:
                if status is not None and task.status != status:
                    continue
                results.append(task)
        return results


# ── PlanOfAction ──────────────────────────────────────────────────────────────

class PlanOfAction:
    PRIORITY_ORDER = {"high": 3, "medium": 2, "low": 1}
    START_MINUTE = 8 * 60  # 8:00 AM as minutes since midnight

    def __init__(self, owner: Owner):
        """Initialize the plan with an owner, pulling their available time and pets."""
        self.owner = owner
        self.available_time = owner.available_time_minutes
        self.scheduled_tasks: list[Task] = []

        # Precomputed after generate_plan()
        self._task_pet_map: dict[Task, str] = {}
        self._time_slots: list[tuple[int, int, Task]] = []  # (start_min, end_min, task)

    def generate_plan(self) -> None:
        """
        Schedule tasks due today that are still pending.

        Sorting: priority descending, then shorter duration first (fits more tasks
        into the available window at equal priority).
        """
        # Build task id → pet name map once for O(1) lookups everywhere.
        # id() is used because Task contains a list field (recurrence_days)
        # which makes Task objects unhashable as dict keys.
        self._task_pet_map = {
            id(task): pet.name
            for pet in self.owner.pets
            for task in pet.tasks
        }

        due_tasks = [
            t for t in self.owner.get_all_tasks()
            if t.is_due_today() and t.status != "complete"
        ]

        sorted_tasks = sorted(
            due_tasks,
            key=lambda t: (self.PRIORITY_ORDER.get(t.priority, 0), -t.duration_minutes),
            reverse=True,
        )

        time_remaining = self.available_time
        self.scheduled_tasks = []
        self._time_slots = []
        current_minute = self.START_MINUTE

        for task in sorted_tasks:
            if task.duration_minutes <= time_remaining:
                start = current_minute
                end = current_minute + task.duration_minutes
                self.scheduled_tasks.append(task)
                self._time_slots.append((start, end, task))
                time_remaining -= task.duration_minutes
                current_minute = end

    # ── Sorting by time ───────────────────────────────────────────────────────

    def get_tasks_sorted_by_time(self) -> list[tuple[str, str, Task]]:
        """
        Return scheduled tasks sorted by start time as (start_str, end_str, task) tuples.

        Tasks are already sequential in this scheduler, but this method normalises
        the output and makes it easy to display or re-sort after manual edits.

        Returns:
            A list of (start, end, task) tuples where start and end are "HH:MM"
            strings, ordered from earliest to latest scheduled start time.
            Returns an empty list if generate_plan() has not been called.
        """
        sorted_slots = sorted(self._time_slots, key=lambda s: s[0])
        return [
            (_minutes_to_time(start), _minutes_to_time(end), task)
            for start, end, task in sorted_slots
        ]

    def sort_by_time(self, tasks: list[Task]) -> list[Task]:
        """
        Sort a list of Task objects by their preferred_time attribute ("HH:MM").

        The tuple key converts each "HH:MM" string into (hours, minutes) integers
        so that "08:05" -> (8, 5) < "08:30" -> (8, 30) < "09:00" -> (9, 0).
        Python compares tuples element-by-element (hours first, then minutes),
        which mirrors natural clock ordering. Tasks with no preferred_time are
        placed at the end using the sentinel value (99, 99).

        Args:
            tasks: A list of Task objects to sort. The original list is not
                   modified — a new sorted list is returned.

        Returns:
            A new list of Task objects ordered by preferred_time, earliest first.
            Tasks without a preferred_time appear at the end, in their original
            relative order.
        """
        return sorted(
            tasks,
            key=lambda t: (
                tuple(int(part) for part in t.preferred_time.split(":"))
                if t.preferred_time is not None
                else (99, 99)
            ),
        )

    # ── Conflict detection ────────────────────────────────────────────────────

    def _pet_of(self, task: Task) -> str:
        """Return the pet name for a task using the precomputed map."""
        return self._task_pet_map.get(id(task), "Unknown")

    def _slots_overlap(self, start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
        """
        Return True if two half-open time windows [start, end) overlap.

        Uses the standard interval-overlap test: two windows overlap when
        A starts before B ends AND B starts before A ends. This is expressed
        as a single boolean: start_a < end_b and start_b < end_a.

        Adjacent windows where end_a == start_b are NOT considered overlapping
        — one task finishing at 08:30 and another starting at 08:30 is a
        back-to-back schedule, not a conflict.

        Args:
            start_a: Start of window A in minutes since midnight.
            end_a:   End of window A in minutes since midnight.
            start_b: Start of window B in minutes since midnight.
            end_b:   End of window B in minutes since midnight.

        Returns:
            True if the two windows share any time, False if they are
            non-overlapping or only touch at a single boundary point.
        """
        return start_a < end_b and start_b < end_a

    def _safe_time_to_minutes(self, time_str: str) -> int | None:
        """
        Fault-tolerant wrapper around _time_to_minutes for use inside conflict
        detection, where a single bad value should never crash the whole scan.

        Attempts to parse a "HH:MM" string into minutes since midnight. If the
        string is malformed (wrong format, letters instead of digits, empty
        string, etc.), catches the resulting ValueError or AttributeError and
        returns None instead of propagating the exception.

        The caller is responsible for checking the return value: when None is
        received it should append a [Warning] message to the conflicts list and
        skip that task with `continue`, allowing the rest of the scan to finish.

        Args:
            time_str: A time string expected to be in "HH:MM" format,
                      e.g. "08:30". Invalid values like "9am" or "" return None.

        Returns:
            An integer representing minutes since midnight (e.g. 510 for "08:30"),
            or None if the string could not be parsed.
        """
        try:
            return _time_to_minutes(time_str)
        except (ValueError, AttributeError):
            return None

    def detect_conflicts(self) -> list[str]:
        """
        Lightweight conflict detection — returns warning strings instead of
        raising exceptions.

        Guard rails:
          - If generate_plan() has not been called yet, returns a single
            warning immediately rather than scanning empty data.
          - Malformed preferred_time values (wrong format, None slipping
            through) are caught by _safe_time_to_minutes and recorded as
            warnings; the rest of the scan continues uninterrupted.
          - Each of the three detection blocks is wrapped in try/except so
            an unexpected error in one block never silences the others.

        Conflict types detected:
          1. Scheduled-slot overlap  — actual _time_slots windows collide.
          2. Preferred-time overlap  — requested windows collide.
          3. Preferred-time mismatch — greedy scheduler placed a task at a
             different time than the owner requested.
        """
        # --- Guard: plan must exist before scanning ---------------------------
        if not self._time_slots:
            return ["[Warning] No scheduled tasks found. Call generate_plan() before detect_conflicts()."]

        conflicts = []

        # --- Conflict type 1: actual scheduled-slot overlaps ------------------
        try:
            for i, (start_a, end_a, task_a) in enumerate(self._time_slots):
                for start_b, end_b, task_b in self._time_slots[i + 1:]:
                    if self._slots_overlap(start_a, end_a, start_b, end_b):
                        pet_a = self._pet_of(task_a)
                        pet_b = self._pet_of(task_b)
                        scope = "same pet" if pet_a == pet_b else "different pets"
                        conflicts.append(
                            f"[Scheduled overlap | {scope}] "
                            f"'{task_a.name}' ({pet_a}, {_minutes_to_time(start_a)}-{_minutes_to_time(end_a)}) "
                            f"overlaps with "
                            f"'{task_b.name}' ({pet_b}, {_minutes_to_time(start_b)}-{_minutes_to_time(end_b)})."
                        )
        except Exception as e:
            conflicts.append(f"[Warning] Scheduled-slot scan failed unexpectedly: {e}")

        # --- Conflict type 2: preferred_time window overlaps ------------------
        try:
            tasks_with_pref = []
            for task in self.owner.get_all_tasks():
                if task.preferred_time is None:
                    continue
                minutes = self._safe_time_to_minutes(task.preferred_time)
                if minutes is None:
                    conflicts.append(
                        f"[Warning] '{task.name}' has an unreadable preferred_time "
                        f"'{task.preferred_time}' -- skipped in overlap check."
                    )
                    continue
                tasks_with_pref.append((task, minutes))

            for i, (task_a, pref_a) in enumerate(tasks_with_pref):
                end_a = pref_a + task_a.duration_minutes
                for task_b, pref_b in tasks_with_pref[i + 1:]:
                    end_b = pref_b + task_b.duration_minutes
                    if self._slots_overlap(pref_a, end_a, pref_b, end_b):
                        pet_a = self._pet_of(task_a)
                        pet_b = self._pet_of(task_b)
                        scope = "same pet" if pet_a == pet_b else "different pets"
                        conflicts.append(
                            f"[Preferred-time overlap | {scope}] "
                            f"'{task_a.name}' ({pet_a}, {task_a.preferred_time}, {task_a.duration_minutes} min) "
                            f"overlaps with "
                            f"'{task_b.name}' ({pet_b}, {task_b.preferred_time}, {task_b.duration_minutes} min)."
                        )
        except Exception as e:
            conflicts.append(f"[Warning] Preferred-time overlap scan failed unexpectedly: {e}")

        # --- Conflict type 3: preferred_time vs actual scheduled slot ---------
        try:
            for start, _, task in self._time_slots:
                if task.preferred_time is None:
                    continue
                preferred_start = self._safe_time_to_minutes(task.preferred_time)
                if preferred_start is None:
                    conflicts.append(
                        f"[Warning] '{task.name}' has an unreadable preferred_time "
                        f"'{task.preferred_time}' -- skipped in mismatch check."
                    )
                    continue
                if preferred_start != start:
                    pet = self._pet_of(task)
                    conflicts.append(
                        f"[Time mismatch | {pet}] "
                        f"'{task.name}' prefers {task.preferred_time} "
                        f"but is scheduled at {_minutes_to_time(start)}."
                    )
        except Exception as e:
            conflicts.append(f"[Warning] Time-mismatch scan failed unexpectedly: {e}")

        return conflicts

    # ── Output helpers ────────────────────────────────────────────────────────

    def get_what(self) -> str:
        """Return a summary of what tasks are scheduled."""
        if not self.scheduled_tasks:
            return "No tasks scheduled. Call generate_plan() first."
        lines = [
            f"- {t.name} ({t.category}): {t.duration_minutes} min [{t.priority} priority]"
            for t in self.scheduled_tasks
        ]
        return "\n".join(lines)

    def get_when(self) -> str:
        """Return a time-slotted schedule starting at 8:00 AM."""
        if not self.scheduled_tasks:
            return "No tasks scheduled. Call generate_plan() first."
        lines = []
        for start, end, task in self._time_slots:
            pet_name = self._task_pet_map.get(id(task), "Unknown")
            lines.append(
                f"{_minutes_to_time(start)} - {_minutes_to_time(end)}: {task.name} for {pet_name}"
            )
        return "\n".join(lines)

    def explain_reasoning(self) -> str:
        """Explain why tasks were chosen and in what order."""
        if not self.scheduled_tasks:
            return "No plan generated yet. Call generate_plan() first."

        all_tasks = self.owner.get_all_tasks()
        skipped = [t for t in all_tasks if t not in self.scheduled_tasks]

        lines = [
            f"Tasks were sorted by priority (high > medium > low) and fit within "
            f"{self.available_time} minutes of available time.",
            "",
            "Scheduled:",
        ]
        for t in self.scheduled_tasks:
            pet_name = self._task_pet_map.get(id(t), "Unknown")
            lines.append(f"  - {t.name} for {pet_name}: {t.priority} priority, {t.duration_minutes} min")

        if skipped:
            lines.append("")
            lines.append("Skipped (not enough time, already complete, or not due today):")
            for t in skipped:
                pet_name = self._task_pet_map.get(id(t), "Unknown")  # bug fix: own lookup per task
                lines.append(f"  - {t.name} for {pet_name}: {t.priority} priority, {t.duration_minutes} min")

        return "\n".join(lines)
