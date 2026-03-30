from pawpal_system import Task, Pet, Owner, PlanOfAction

# ---------------------------------------------------------------------------
# Two tasks deliberately set to the same preferred_time
# ---------------------------------------------------------------------------

mochi = Pet(name="Mochi", breed="Shiba Inu", age=3, sex="Male")
luna  = Pet(name="Luna",  breed="Tabby Cat",  age=2, sex="Female")

# Same-pet conflict: both of Mochi's tasks want 08:00
mochi.add_task(Task(name="Morning Walk", category="walk",    duration_minutes=30, priority="high", preferred_time="08:00"))
mochi.add_task(Task(name="Breakfast",    category="feeding", duration_minutes=10, priority="high", preferred_time="08:00"))

# Cross-pet conflict: Luna's Meds also want 08:00
luna.add_task(Task(name="Flea Meds",    category="meds",    duration_minutes=5,  priority="high", preferred_time="08:00"))

# No conflict: Luna's dinner is at a different time
luna.add_task(Task(name="Dinner",       category="feeding", duration_minutes=10, priority="medium", preferred_time="18:00"))

owner = Owner(name="Jordan", available_time_minutes=90)
owner.add_pet(mochi)
owner.add_pet(luna)

plan = PlanOfAction(owner)
plan.generate_plan()

print("=" * 56)
print("  Scheduled tasks")
print("=" * 56)
print(plan.get_when())

print("\n" + "=" * 56)
print("  Conflict detection results")
print("=" * 56)
conflicts = plan.detect_conflicts()
print(f"  Conflicts found: {len(conflicts)}\n")
for msg in conflicts:
    print(f"  {msg}")
