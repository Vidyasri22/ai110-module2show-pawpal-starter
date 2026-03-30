import streamlit as st
from pawpal_system import Task, Pet, Owner, PlanOfAction

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
st.title("🐾 PawPal+")

st.divider()

# ── Section 1: Owner & Pet Setup ─────────────────────────────────────────────
st.subheader("Owner & Pet Setup")

col1, col2 = st.columns(2)
with col1:
    owner_name = st.text_input("Owner name", value="Jordan")
    available_time = st.number_input("Available time today (minutes)", min_value=10, max_value=480, value=60)
with col2:
    pet_name = st.text_input("Pet name", value="Mochi")
    breed = st.text_input("Breed", value="Shiba Inu")
    pet_age = st.number_input("Pet age", min_value=0, max_value=30, value=3)
    pet_sex = st.selectbox("Sex", ["Male", "Female"])

if st.button("Save owner & pet"):
    pet = Pet(name=pet_name, breed=breed, age=int(pet_age), sex=pet_sex)
    owner = Owner(name=owner_name, available_time_minutes=int(available_time))
    owner.add_pet(pet)
    st.session_state.owner = owner
    st.session_state.plan = None
    st.success(f"Saved {owner_name} with pet {pet_name}!")

st.divider()

# ── Section 2: Add Tasks ──────────────────────────────────────────────────────
st.subheader("Add Tasks")

col1, col2, col3, col4 = st.columns(4)
with col1:
    task_title = st.text_input("Task name", value="Morning walk")
with col2:
    category = st.selectbox("Category", ["walk", "feeding", "meds", "grooming"])
with col3:
    duration = st.number_input("Duration (min)", min_value=1, max_value=240, value=20)
with col4:
    priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)

col5, col6 = st.columns(2)
with col5:
    preferred_time = st.text_input("Preferred time (HH:MM, optional)", value="", placeholder="e.g. 08:30")
with col6:
    recurrence = st.selectbox("Repeats", ["none", "daily", "weekly"])

if st.button("Add task"):
    if "owner" not in st.session_state:
        st.warning("Please save an owner & pet first.")
    else:
        pref_time_value = preferred_time.strip() if preferred_time.strip() else None
        recurrence_value = None if recurrence == "none" else recurrence
        task = Task(
            name=task_title,
            category=category,
            duration_minutes=int(duration),
            priority=priority,
            preferred_time=pref_time_value,
            recurrence=recurrence_value,
        )
        st.session_state.owner.pets[0].add_task(task)
        st.session_state.plan = None
        st.success(f"Added: {task_title} ({category}, {duration} min, {priority} priority)")

# ── Task table sorted by preferred time ──────────────────────────────────────
if "owner" in st.session_state:
    all_tasks = st.session_state.owner.get_all_tasks()
    if all_tasks:
        # Use PlanOfAction.sort_by_time() so tasks with a preferred_time appear
        # in clock order; tasks without one float to the end.
        _sorter = PlanOfAction(st.session_state.owner)
        sorted_tasks = _sorter.sort_by_time(all_tasks)

        PRIORITY_ICON = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        RECURRENCE_LABEL = {"daily": "Daily", "weekly": "Weekly", None: "One-time"}

        st.table([
            {
                "Task": t.name,
                "Category": t.category.capitalize(),
                "Duration (min)": t.duration_minutes,
                "Priority": f"{PRIORITY_ICON.get(t.priority, '')} {t.priority.capitalize()}",
                "Preferred time": t.preferred_time or "—",
                "Repeats": RECURRENCE_LABEL.get(t.recurrence, "One-time"),
                "Status": t.status.capitalize(),
            }
            for t in sorted_tasks
        ])
    else:
        st.info("No tasks yet. Add one above.")

st.divider()

# ── Section 3: Generate Schedule ─────────────────────────────────────────────
st.subheader("Generate Schedule")

if st.button("Generate schedule"):
    if "owner" not in st.session_state:
        st.warning("Please save an owner & pet first.")
    elif not st.session_state.owner.get_all_tasks():
        st.warning("Please add at least one task first.")
    else:
        plan = PlanOfAction(st.session_state.owner)
        plan.generate_plan()
        st.session_state.plan = plan

if "plan" in st.session_state and st.session_state.plan is not None:
    plan = st.session_state.plan

    # ── Conflict warnings ─────────────────────────────────────────────────────
    # Shown before the schedule so owners can act on them immediately.
    conflicts = plan.detect_conflicts()
    # Filter out the "call generate_plan first" guard message — plan is ready.
    real_conflicts = [c for c in conflicts if "Call generate_plan" not in c]

    if real_conflicts:
        st.warning(
            f"⚠️ **{len(real_conflicts)} scheduling issue(s) found.** "
            "Review the details below before following this plan."
        )
        for conflict in real_conflicts:
            # Translate the internal prefix into a plain-English label.
            if conflict.startswith("[Scheduled overlap"):
                label = "**Time overlap in your schedule**"
                tip = "Two tasks are assigned to the same time slot. Try removing or shortening one."
            elif conflict.startswith("[Preferred-time overlap"):
                label = "**Conflicting preferred times**"
                tip = "Two tasks are requested at overlapping times. Adjust a preferred time so they don't clash."
            elif conflict.startswith("[Time mismatch"):
                label = "**Task placed at a different time than requested**"
                tip = "The scheduler couldn't fit this task at your preferred time and moved it."
            else:
                label = "**Note**"
                tip = ""

            # Strip the bracketed prefix to keep the detail readable.
            detail = conflict.split("]", 1)[-1].strip() if "]" in conflict else conflict

            with st.expander(f"{label} — click to see details"):
                st.write(detail)
                if tip:
                    st.caption(f"Suggestion: {tip}")
    else:
        st.success("No scheduling conflicts — your plan looks good!")

    # ── Timeline table ────────────────────────────────────────────────────────
    st.markdown("**Your schedule for today**")
    time_slots = plan.get_tasks_sorted_by_time()
    if time_slots:
        st.table([
            {
                "Time": f"{start} – {end}",
                "Task": task.name,
                "Category": task.category.capitalize(),
                "Duration (min)": task.duration_minutes,
                "Priority": f"{PRIORITY_ICON.get(task.priority, '')} {task.priority.capitalize()}",
            }
            for start, end, task in time_slots
        ])
    else:
        st.info("No tasks fit within your available time today.")

    # ── Reasoning ────────────────────────────────────────────────────────────
    with st.expander("Why did the scheduler choose this plan?"):
        st.text(plan.explain_reasoning())
