# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

My initial design had 3 classes:

- **Pet**: stores basic pet info like name, age, breed, and sex.
- **PetTasks**: represented care activities with walking, feeding, meds, and grooming as fixed methods.
- **PlanOfAction**: listed all the tasks and showed what needed to be done and when.

**b. Design changes**

Yes, two things changed during implementation:

1. **PetTasks became a Task dataclass** — having fixed methods didn't work because the scheduler needs `duration_minutes` and `priority` to make decisions, and users need to add tasks dynamically. Making each task its own object with attributes solved both problems.

2. **Owner class was added** — I realized the available time constraint belongs to the owner, not the pet. So I added an `Owner` class to hold `name` and `available_time_minutes`.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

The scheduler uses three constraints:

- **Available time** — hard limit. No task gets scheduled if it won't fit in the remaining time.
- **Priority** — tasks are sorted high → medium → low before scheduling, since meds and feeding matter more than grooming.
- **Preferred time** — soft constraint used only for conflict warnings, not for reordering. Enforcing it strictly would block high-priority tasks from being scheduled if their preferred slot was already taken.

**b. Tradeoffs**

The scheduler is greedy it sorts by priority and fits tasks in one by one starting at 8:00 AM. It never looks ahead to see if skipping one task would let two others fit. This is a reasonable tradeoff for pet care because priority reflects real urgency, and the greedy result is almost always the same as the optimal one for fewer than a dozen tasks a day. A full knapsack solution would be overkill here.

---

## 3. AI Collaboration

**a. How you used AI**

I used Copilot at every stage, but in different ways depending on the task:

- **`#codebase` queries** were the most useful. Asking things like "what edge cases should I test for a pet scheduler?" with `#codebase` gave answers tied to my actual class names and field types, not generic examples.
- **Inline completions** saved time on repetitive work like writing the second and third test functions once the first one was set up.
- **Separate chat sessions per phase** kept things focused. I didn't want testing questions mixed in with UI questions switching sessions forced a natural checkpoint between phases.

The best prompt pattern I found was to name the specific method and ask for the reasoning, not just the code. "Explain why sort_by_time uses a tuple key" was more useful than "write a sort function."

**b. Judgment and verification**

When Copilot generated `test_detect_conflicts_flags_duplicate_preferred_times`, it asserted `len(conflicts) >= 1` on the whole conflict list. That looked fine at first, but I noticed that `detect_conflicts()` returns three different types of messages  overlaps, mismatches, and warnings. The test would have passed even if only a mismatch warning fired, which wasn't what I was testing for.

I changed it to filter first:

```python
overlap_conflicts = [c for c in conflicts if "overlap" in c.lower()]
assert len(overlap_conflicts) >= 1
```

The fix only made sense after reading the source. Running the test wasn't enough. I had to understand what else could make it pass unexpectedly.

---

## 4. Testing and Verification

**a. What you tested**

I wrote 10 tests across four areas:

- **Task basics** — tasks start as pending, `mark_complete()` works, `add_task()` grows the list correctly.
- **Sorting** — `sort_by_time()` returns tasks in clock order, and tasks without a preferred time go to the end.
- **Recurrence** — completing a daily task creates a new one due tomorrow; completing a one-time task doesn't create anything.
- **Conflict detection** — duplicate preferred times trigger an overlap warning; a clean schedule produces none.

These areas cover the behaviors most likely to break quietly sorting wrong order or recurrence creating duplicates wouldn't crash the app, they'd just show the owner bad data.

**b. Confidence**

**4 / 5.** The core logic all passes. The missing star is for things not yet tested: the greedy scheduler's edge cases (zero time, task that exactly fills the window), weekly recurrence, `filter_tasks()` with both parameters, and the Streamlit UI. The greedy scheduler tests would be my next priority since that's the heart of the app.

---

## 5. Reflection

**a. What went well**

I'm most happy with how `detect_conflicts()` turned out. It was the trickiest method three conflict types, bad input that shouldn't crash the whole scan, and output that needed to be readable in the UI. Returning warning strings instead of raising exceptions was the right call, and it paid off when the Streamlit UI could parse the prefixes and show a helpful message for each one.

**b. What you would improve**

Two things I'd fix in a next version:

1. The UI only handles one pet (`owner.pets[0]` is hardcoded in `app.py`). The backend already supports multiple pets, so adding a pet selector dropdown would unlock that.
2. The task table sorts by preferred time but the generated schedule sorts by priority. Showing the same tasks in two different orders on the same screen is confusing. I'd add a toggle so the user picks one view.

**c. Key takeaway**

AI speeds up the work, but it can't make the design decisions for you. Every real choice in this project how strict to make preferred time, whether to use exceptions or warning strings, what exactly to assert in a test needed me to understand the tradeoff first. The Copilot suggestion that looked correct but wasn't caught me off guard. It passed the test. I had to read the code to see why it was still wrong. That's the part AI can't do: asking "what else could make this pass that I didn't intend?"
