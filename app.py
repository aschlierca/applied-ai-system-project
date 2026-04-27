from __future__ import annotations

import os

import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from pawpal_system import Pet, Scheduler, Task, User
from guardrails import ValidationError, validate_duration, validate_priority, validate_time_available
from logger_config import get_memory_logs, setup_logger
from ai_assistant import AIAssistant

logger = setup_logger("app")

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

# ── Session-state initialisation ───────────────────────────────────────────────

def _init_state() -> None:
    if "owner" not in st.session_state:
        st.session_state.owner = User(
            name="", owner_preferences={}, time_available_minutes=60
        )
    if "next_pet_id" not in st.session_state:
        st.session_state.next_pet_id = 1
    if "next_task_id" not in st.session_state:
        st.session_state.next_task_id = 1
    if "last_result" not in st.session_state:
        st.session_state.last_result = None


_init_state()
owner: User = st.session_state.owner

# ── Sidebar — owner controls ───────────────────────────────────────────────────

with st.sidebar:
    st.header("👤 Owner Settings")

    owner_name_in = st.text_input("Your name", value=owner.name or "")
    time_avail_in = st.number_input(
        "Time available today (minutes)",
        min_value=5,
        max_value=1440,
        value=max(owner.time_available_minutes, 5),
        step=5,
    )
    api_key_in = st.text_input(
        "Anthropic API Key",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
        type="password",
        help="Required for AI-powered explanations. Set ANTHROPIC_API_KEY in a .env file or enter it here.",
    )

    if st.button("💾 Save settings", use_container_width=True):
        try:
            vt = validate_time_available(time_avail_in)
            owner.name = owner_name_in.strip() or "Owner"
            owner.time_available_minutes = vt
            if api_key_in:
                os.environ["ANTHROPIC_API_KEY"] = api_key_in
            logger.info(
                "Owner settings saved — name: %s, time: %d min", owner.name, vt
            )
            st.success("Settings saved!")
        except ValidationError as exc:
            st.error(str(exc))

    st.divider()
    total_tasks = sum(len(p.tasks) for p in owner.pets)
    st.caption(f"Pets: {len(owner.pets)}  ·  Tasks: {total_tasks}")

# ── Title ──────────────────────────────────────────────────────────────────────

st.title("🐾 PawPal+")
st.caption("AI-powered pet care planner with RAG-enhanced insights")

# ── Tabs ───────────────────────────────────────────────────────────────────────

tab_pets, tab_schedule, tab_logs = st.tabs(
    ["🐕 Pets & Tasks", "📅 Schedule & AI Insights", "📋 Activity Log"]
)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Pets & Tasks
# ═══════════════════════════════════════════════════════════════════════════════

with tab_pets:
    st.subheader("Add a Pet")

    with st.form("add_pet_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        pet_name_in = c1.text_input("Pet name", placeholder="Mochi")
        species_in = c2.selectbox(
            "Species",
            ["dog", "cat", "rabbit", "bird", "hamster", "guinea pig", "other"],
        )
        age_in = c3.number_input(
            "Age (years)", min_value=0.0, max_value=30.0, value=2.0, step=0.5
        )
        add_pet_btn = st.form_submit_button("➕ Add Pet", use_container_width=True)

    if add_pet_btn:
        pname = pet_name_in.strip()
        if not pname:
            st.error("Pet name cannot be empty.")
        else:
            try:
                new_pet = Pet(
                    id=st.session_state.next_pet_id,
                    name=pname,
                    species=species_in,
                    age_years=age_in,
                )
                owner.add_pet(new_pet)
                st.session_state.next_pet_id += 1
                st.success(f"Added {pname}!")
            except ValueError as exc:
                st.error(str(exc))

    st.divider()

    if not owner.pets:
        st.info("No pets yet. Add one above to get started.")
    else:
        for pet in owner.pets:
            with st.expander(
                f"🐾 **{pet.name}** — {pet.species}, {pet.age_years} yr",
                expanded=True,
            ):
                tasks = pet.list_tasks()
                if tasks:
                    st.table([t.to_dict() for t in tasks])
                else:
                    st.caption("No tasks added yet.")

                st.markdown("**Add a task**")
                with st.form(f"task_form_{pet.id}", clear_on_submit=True):
                    r1a, r1b = st.columns(2)
                    t_name = r1a.text_input(
                        "Task name", placeholder="Morning walk", key=f"tn_{pet.id}"
                    )
                    t_cat = r1b.selectbox(
                        "Category",
                        ["exercise", "feeding", "medication", "grooming", "enrichment", "other"],
                        key=f"tc_{pet.id}",
                    )
                    r2a, r2b, r2c = st.columns(3)
                    t_dur = r2a.number_input(
                        "Duration (min)", min_value=1, max_value=240, value=20, key=f"td_{pet.id}"
                    )
                    t_pri = r2b.selectbox(
                        "Priority (1–10)",
                        [1, 2, 3, 5, 8, 10],
                        index=3,
                        key=f"tp_{pet.id}",
                    )
                    t_time = r2c.text_input(
                        "Start time (HH:MM)", value="08:00", key=f"tt_{pet.id}"
                    )
                    t_rec = st.selectbox(
                        "Recurrence",
                        ["none", "daily", "weekly"],
                        key=f"tr_{pet.id}",
                    )
                    add_task_btn = st.form_submit_button(
                        "➕ Add Task", use_container_width=True
                    )

                if add_task_btn:
                    try:
                        vdur = validate_duration(t_dur)
                        vpri = validate_priority(t_pri)
                        tname = t_name.strip() or "Task"
                        rec = None if t_rec == "none" else t_rec
                        new_task = Task(
                            id=st.session_state.next_task_id,
                            name=tname,
                            starting_time=t_time,
                            category=t_cat,
                            duration_minutes=vdur,
                            priority=vpri,
                            recurrence=rec,
                        )
                        pet.add_task(new_task)
                        st.session_state.next_task_id += 1
                        logger.info(
                            "Task '%s' added to %s (priority=%d, %d min, cat=%s)",
                            tname, pet.name, vpri, vdur, t_cat,
                        )
                        st.success(f"Added '{tname}'!")
                        st.rerun()
                    except (ValidationError, ValueError) as exc:
                        st.error(str(exc))

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Schedule & AI Insights
# ═══════════════════════════════════════════════════════════════════════════════

with tab_schedule:
    if not owner.pets:
        st.info("Add a pet in the **Pets & Tasks** tab first.")
    else:
        pet_map = {p.name: p for p in owner.pets}
        selected_name = st.selectbox("Select pet to schedule", list(pet_map.keys()))
        selected_pet: Pet = pet_map[selected_name]

        col_btn, col_metric = st.columns([3, 1])
        col_metric.metric("Time budget", f"{owner.time_available_minutes} min")

        if col_btn.button(
            "🗓 Generate Schedule + AI Insights",
            use_container_width=True,
            type="primary",
        ):
            if not selected_pet.tasks:
                st.warning("This pet has no tasks. Add tasks in the Pets & Tasks tab first.")
            else:
                with st.spinner("Generating schedule and retrieving pet care insights…"):
                    try:
                        schedule = owner.generate_schedule_for_pet(selected_pet.id)

                        sched_obj = Scheduler(
                            pet=selected_pet,
                            user_prefs=owner.owner_preferences,
                        )
                        conflict_msg = sched_obj.detect_time_conflicts(
                            pets=owner.pets,
                            time_available=owner.time_available_minutes,
                        )

                        ai_text: str | None = None
                        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
                        if api_key and schedule:
                            try:
                                assistant = AIAssistant(api_key=api_key)
                                items_for_ai = [
                                    {
                                        "name": si.task.name,
                                        "duration": si.task.duration_minutes,
                                        "priority": si.task.priority,
                                        "category": si.task.category,
                                    }
                                    for si in schedule
                                ]
                                ai_text = assistant.explain_schedule(
                                    pet_name=selected_pet.name,
                                    species=selected_pet.species,
                                    age_years=selected_pet.age_years,
                                    schedule_items=items_for_ai,
                                    time_available=owner.time_available_minutes,
                                )
                            except Exception as exc:
                                logger.error("AI explanation failed: %s", exc)
                                ai_text = None

                        st.session_state.last_result = {
                            "pet_name": selected_pet.name,
                            "schedule": schedule,
                            "conflict_msg": conflict_msg,
                            "ai_text": ai_text,
                        }

                    except Exception as exc:
                        logger.error("Schedule generation error: %s", exc)
                        st.error(f"Error: {exc}")

        # ── Display last result ────────────────────────────────────────────────

        result = st.session_state.last_result
        if result:
            st.subheader(f"Schedule for {result['pet_name']}")

            rows = [
                {
                    "Task": si.task.name,
                    "Category": si.task.category,
                    "Start (min)": si.start_minute,
                    "End (min)": si.end_minute,
                    "Duration (min)": si.task.duration_minutes,
                    "Priority": si.task.priority,
                }
                for si in result["schedule"]
            ]
            if rows:
                st.table(rows)
            else:
                st.info("No tasks fit within the available time budget.")

            cflct = result.get("conflict_msg", "")
            if cflct and "⚠" in cflct:
                st.warning(cflct)
            else:
                st.success(cflct or "No conflicts detected.")

            if result.get("ai_text"):
                st.subheader("🤖 AI Insights (RAG-enhanced)")
                st.markdown(result["ai_text"])
            elif not os.environ.get("ANTHROPIC_API_KEY"):
                st.info(
                    "Enter your Anthropic API key in the sidebar to enable AI-powered explanations."
                )

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Activity Log
# ═══════════════════════════════════════════════════════════════════════════════

with tab_logs:
    st.subheader("Activity Log")
    st.caption(
        "All INFO+ events from this session are captured here and written to "
        "logs/pawpal_YYYYMMDD.log."
    )

    logs = get_memory_logs()
    if logs:
        # Show most-recent entries first, cap at 100
        log_text = "\n".join(reversed(logs[-100:]))
        st.code(log_text, language=None)
    else:
        st.info("No log entries yet. Generate a schedule or add pets to see activity.")

    if st.button("🔄 Refresh log"):
        st.rerun()
