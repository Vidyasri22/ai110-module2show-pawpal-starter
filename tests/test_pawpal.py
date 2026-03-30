import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, timedelta
from pawpal_system import Task, Pet, Owner, PlanOfAction


def test_task_starts_as_pending():
    task = Task(name="Morning Walk", category="walk", duration_minutes=30, priority="high")
    assert task.status == "pending"


def test_mark_complete_changes_status():
    task = Task(name="Morning Walk", category="walk", duration_minutes=30, priority="high")
    task.mark_complete()
    assert task.status == "complete"


def test_add_task_increases_pet_task_count():
    pet = Pet(name="Mochi", breed="Shiba Inu", age=3, sex="Male")
    assert len(pet.tasks) == 0

    task = Task(name="Breakfast", category="feeding", duration_minutes=10, priority="high")
    pet.add_task(task)
    assert len(pet.tasks) == 1


def test_add_multiple_tasks_increases_count_correctly():
    pet = Pet(name="Luna", breed="Tabby Cat", age=2, sex="Female")
    pet.add_task(Task(name="Flea Medicine", category="meds", duration_minutes=5, priority="medium"))
    pet.add_task(Task(name="Grooming", category="grooming", duration_minutes=20, priority="low"))
    assert len(pet.tasks) == 2


# ── Sorting ───────────────────────────────────────────────────────────────────

def test_sort_by_time_returns_tasks_in_chronological_order():
    """Tasks with preferred_time set should come back earliest-first."""
    owner = Owner(name="Alex", available_time_minutes=120)
    pet = Pet(name="Mochi", breed="Shiba Inu", age=3, sex="Male")
    walk   = Task(name="Morning Walk",  category="walk",    duration_minutes=30, priority="high",   preferred_time="09:00")
    meds   = Task(name="Medication",    category="meds",    duration_minutes=10, priority="medium", preferred_time="07:30")
    groom  = Task(name="Grooming",      category="grooming",duration_minutes=20, priority="low",    preferred_time="08:15")
    for t in (walk, meds, groom):
        pet.add_task(t)
    owner.add_pet(pet)
    plan = PlanOfAction(owner)

    sorted_tasks = plan.sort_by_time([walk, meds, groom])
    times = [t.preferred_time for t in sorted_tasks]
    assert times == ["07:30", "08:15", "09:00"]


def test_sort_by_time_places_none_preferred_time_at_end():
    """Tasks without a preferred_time should sort to the end of the list."""
    owner = Owner(name="Alex", available_time_minutes=120)
    pet = Pet(name="Mochi", breed="Shiba Inu", age=3, sex="Male")
    walk    = Task(name="Morning Walk", category="walk",    duration_minutes=30, priority="high",   preferred_time="08:00")
    no_time = Task(name="Free Play",    category="walk",    duration_minutes=15, priority="low",    preferred_time=None)
    for t in (walk, no_time):
        pet.add_task(t)
    owner.add_pet(pet)
    plan = PlanOfAction(owner)

    sorted_tasks = plan.sort_by_time([no_time, walk])
    assert sorted_tasks[0].name == "Morning Walk"
    assert sorted_tasks[-1].preferred_time is None


# ── Recurrence ────────────────────────────────────────────────────────────────

def test_marking_daily_task_complete_creates_next_day_task():
    """Completing a daily task should append a new pending task due tomorrow."""
    pet = Pet(name="Mochi", breed="Shiba Inu", age=3, sex="Male")
    feeding = Task(name="Breakfast", category="feeding", duration_minutes=10,
                   priority="high", recurrence="daily")
    pet.add_task(feeding)

    next_task = pet.mark_task_complete("Breakfast")

    # Original task is now complete
    assert pet.tasks[0].status == "complete"
    # A second task was appended
    assert len(pet.tasks) == 2
    # The new task is pending and due tomorrow
    tomorrow = date.today() + timedelta(days=1)
    assert next_task is not None
    assert next_task.status == "pending"
    assert next_task.due_date == tomorrow


def test_marking_one_time_task_complete_does_not_create_next_task():
    """Completing a one-time task should NOT append any follow-up task."""
    pet = Pet(name="Luna", breed="Tabby Cat", age=2, sex="Female")
    grooming = Task(name="Bath", category="grooming", duration_minutes=20,
                    priority="medium", recurrence=None)
    pet.add_task(grooming)

    result = pet.mark_task_complete("Bath")

    assert result is None
    assert len(pet.tasks) == 1
    assert pet.tasks[0].status == "complete"


# ── Conflict detection ────────────────────────────────────────────────────────

def test_detect_conflicts_flags_duplicate_preferred_times():
    """Two tasks requesting the exact same preferred_time should produce a conflict."""
    owner = Owner(name="Alex", available_time_minutes=120)
    pet = Pet(name="Mochi", breed="Shiba Inu", age=3, sex="Male")
    walk  = Task(name="Morning Walk", category="walk",    duration_minutes=30, priority="high",   preferred_time="08:00")
    meds  = Task(name="Medication",   category="meds",    duration_minutes=10, priority="medium", preferred_time="08:00")
    for t in (walk, meds):
        pet.add_task(t)
    owner.add_pet(pet)

    plan = PlanOfAction(owner)
    plan.generate_plan()
    conflicts = plan.detect_conflicts()

    overlap_conflicts = [c for c in conflicts if "overlap" in c.lower()]
    assert len(overlap_conflicts) >= 1


def test_detect_conflicts_returns_empty_for_clean_schedule():
    """A schedule with no overlapping times should produce zero conflicts."""
    owner = Owner(name="Alex", available_time_minutes=120)
    pet = Pet(name="Mochi", breed="Shiba Inu", age=3, sex="Male")
    walk  = Task(name="Morning Walk", category="walk",    duration_minutes=30, priority="high",   preferred_time="08:00")
    meds  = Task(name="Medication",   category="meds",    duration_minutes=10, priority="medium", preferred_time="09:00")
    for t in (walk, meds):
        pet.add_task(t)
    owner.add_pet(pet)

    plan = PlanOfAction(owner)
    plan.generate_plan()
    conflicts = plan.detect_conflicts()

    overlap_conflicts = [c for c in conflicts if "overlap" in c.lower()]
    assert len(overlap_conflicts) == 0


if __name__ == "__main__":
    test_task_starts_as_pending()
    print("PASS: task starts as pending")

    test_mark_complete_changes_status()
    print("PASS: mark_complete() changes status to complete")

    test_add_task_increases_pet_task_count()
    print("PASS: adding a task increases pet task count")

    test_add_multiple_tasks_increases_count_correctly()
    print("PASS: adding multiple tasks tracks count correctly")

    print("\nAll tests passed.")
