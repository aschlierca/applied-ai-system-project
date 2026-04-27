# PawPal+ — AI-Powered Pet Care Planner

A Streamlit app that helps busy pet owners plan and understand their pet's daily care schedule, extended with Retrieval-Augmented Generation (RAG), a Claude API integration, structured logging, and input guardrails.

---

## Original Project (Modules 1–3)

**Original project name:** PawPal+ (Module 2 Scheduling System)

PawPal+ was originally a rule-based scheduling assistant for pet owners. It allowed users to define pets and care tasks, then used a deterministic greedy algorithm to produce a prioritised daily schedule given the owner's available time. The system included five unit tests covering core behaviours (task completion, recurrence, sorting, and conflict detection) and a basic Streamlit interface.

---

## Title and Summary

**PawPal+ AI** is a pet care planning assistant that combines algorithmic scheduling with AI-generated explanations grounded in a veterinary knowledge base. When a user generates a schedule, the system retrieves the most relevant pet care documentation for that species and task set, injects it into a Claude API prompt, and returns a personalised, evidence-based explanation of why the schedule makes sense for that specific pet. This matters because scheduling software typically tells you *what* to do without explaining *why* — the RAG layer closes that gap.

---

## Architecture Overview

See [diagram.md](diagram.md) for the full Mermaid diagram.

**Key components:**

| Component | File(s) | Role |
|-----------|---------|------|
| Streamlit UI | `app.py` | 3-tab interface: pet/task management, schedule + AI insights, activity log |
| Scheduler | `pawpal_system.py` | Greedy priority-based daily scheduler |
| Input Guardrails | `guardrails.py` | Validates all user inputs before processing |
| Document Retriever | `rag/retriever.py` | Keyword-overlap search over the pet care knowledge base |
| Knowledge Base | `rag/documents/*.txt` | Dog care, cat care, and general pet care guides |
| AI Assistant | `ai_assistant.py` | RAG → Claude API → contextualised schedule explanation |
| Logger | `logger_config.py` | File handler (DEBUG+) and in-app memory handler (INFO+) |
| Tests | `test/test.py`, `test/test_rag.py` | 28 automated tests |

**Data flow:** User input → guardrail validation → greedy scheduling → RAG retrieval (species + task categories as query) → Claude API (retrieved docs injected as context) → AI explanation displayed in Streamlit.

---

## Setup Instructions

### Prerequisites
- Python 3.10 or later (tested on 3.12)
- An Anthropic API key (for AI explanations — the scheduler works without one)

### Steps

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd applied-ai-system-final

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your Anthropic API key (optional — enables AI explanations)
#    Option A: create a .env file
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

#    Option B: enter it in the app sidebar at runtime

# 5. Run the app
streamlit run app.py
```

### Running tests

```bash
pytest test/ -v
# Expected: 28 passed
```

---

## Sample Interactions

### Example 1 — Dog with mixed tasks

**Input:** Mochi, 3-year-old dog, 60 minutes available.
Tasks: Morning walk (exercise, 30 min, priority 8), Feeding (feeding, 10 min, priority 10), Medication (medication, 5 min, priority 9), Puzzle toy (enrichment, 20 min, priority 5).

**Schedule output:**

| Task | Category | Start | End | Duration | Priority |
|------|----------|-------|-----|----------|----------|
| Feeding | feeding | 0 | 10 | 10 min | 10 |
| Medication | medication | 10 | 15 | 5 min | 9 |
| Morning walk | exercise | 15 | 45 | 30 min | 8 |
| Puzzle toy | enrichment | 45 | 65 | 20 min | 5 |

**AI Insight (excerpt):**
> "Starting with Feeding and Medication makes excellent sense for Mochi. Dogs benefit from having medication administered with food to reduce stomach upset, and maintaining consistent feeding times twice daily helps prevent bloat — particularly important for a dog Mochi's size. The 30-minute Morning walk follows naturally after the stomach has had time to settle (about 5–10 minutes), which aligns with veterinary guidance to avoid vigorous exercise immediately after eating..."

---

### Example 2 — Cat with limited time

**Input:** Luna, 5-year-old cat, 25 minutes available.
Tasks: Feeding (feeding, 10 min, priority 10), Play session (enrichment, 15 min, priority 7), Grooming (grooming, 20 min, priority 4).

**Schedule output:**

| Task | Category | Start | End | Duration | Priority |
|------|----------|-------|-----|----------|----------|
| Feeding | feeding | 0 | 10 | 10 min | 10 |
| Play session | enrichment | 10 | 25 | 15 min | 7 |

*(Grooming excluded — insufficient time remaining)*

**Conflict check:** ✓ No conflicts: Luna: 45 min needed but 25 min scheduled (greedy fit).

**AI Insight (excerpt):**
> "This schedule is well-suited for Luna's crepuscular nature. Cats are most active at dawn and dusk, so scheduling the interactive play session immediately after feeding takes advantage of the energy spike cats experience after meals. The documentation notes that wand toys and prey-simulating movement are most engaging for cats at these activity peaks..."

---

### Example 3 — Invalid input caught by guardrails

**Input:** Duration set to `0` minutes, priority set to `15`.

**Result:** Two validation errors displayed immediately:
```
Duration must be a positive number (got 0)
Priority must be between 1 and 10 (got 15)
```
Both are logged at ERROR level in the Activity Log tab and the `logs/pawpal_DATE.log` file. No schedule is generated.

---

## Design Decisions

**Why a keyword-based retriever (no vector DB)?**
Using word-overlap scoring means zero extra dependencies beyond what's already in `requirements.txt`. The knowledge base is small (three files, ~80 paragraphs) and the queries are structured (species + category names), so simple keyword matching achieves high recall without the complexity of embeddings, FAISS, or a hosted vector store. The trade-off is that semantic synonyms ("stroll" vs "walk") may miss some relevant chunks, but for a structured domain like pet care task categories this rarely matters in practice.

**Why greedy scheduling?**
The greedy algorithm is deterministic, explainable, and O(n log n). For the scale of this problem (single owner, handful of pets, <20 tasks per day), optimal scheduling via dynamic programming or ILP would add complexity with no perceivable benefit. The greedy approach also makes the AI's explanation task easier — there are no complex trade-offs to justify.

**Why prompt caching on the system prompt?**
The system prompt in `ai_assistant.py` is identical for every call. Setting `cache_control: ephemeral` on it means repeated calls within a session hit the Anthropic prompt cache, reducing latency and cost by reusing the cached prefix rather than re-tokenising it each time.

**Why module-level log accumulation (not session state)?**
Streamlit reruns the entire script on every interaction, making it awkward to persist a logger handler inside session state. A module-level `_memory_logs` list in `logger_config.py` persists across Streamlit reruns for the lifetime of the server process, which is exactly the scope we want for an in-app activity log.

---

## Testing Summary

**28 tests total — 28 passed (100%)**

| Test file | Tests | Focus |
|-----------|-------|-------|
| `test/test.py` | 5 | Core scheduler: mark_complete, add_task, sort_by_time, recurrence, conflict detection |
| `test/test_rag.py` | 23 | Retriever loading/retrieval, guardrail validation (duration, priority, time format, pet name) |

**What worked well:** Guardrail tests caught every edge case immediately. Retriever tests confirmed that species-specific queries reliably surface species-specific chunks (e.g., "cat feeding" returns cat-related documentation, not dog or general care).

**What didn't work / limitations:** The retriever uses frequency-weighted word overlap, so a query with very common words ("care pet daily") scores many chunks similarly and the top result can be noisy. This would be addressed in a future iteration by using BM25 or embedding-based retrieval.

**Confidence scoring:** Not implemented as a numeric score, but the system communicates confidence implicitly — if fewer than `top_k` non-trivial chunks are found, fewer are injected, and Claude's response naturally hedges more. The Activity Log shows the retrieval score for each query, which functions as a proxy confidence signal.

---

## Reflection

### What this project taught me about AI and problem-solving

Building the RAG layer made concrete something that is easy to miss when just calling an LLM: *the quality of the answer is bounded by the quality of the context*. Claude's schedule explanations became dramatically more specific and useful once the retrieved pet care documentation was included — without it, the model produced generic advice that could apply to any pet. This taught me to think of prompt engineering and knowledge retrieval as equally important engineering problems.

The logging system also changed how I debugged the app. Being able to see the retrieval score and chunk count in the Activity Log made it immediately obvious when a query was returning weak matches, without needing to print anything to a terminal.

### Limitations and biases

- The knowledge base covers only dogs, cats, and general care. Queries for rabbits, birds, or reptiles will return less relevant results.
- The retriever has no semantic understanding — it cannot recognise that "stroll" and "walk" are the same concept.
- Claude's explanations are grounded in the provided documentation but may still reflect biases present in that text (e.g., recommendations skewed toward Western veterinary practice or certain breed types).
- The system has no memory between sessions; all data is lost on page reload.

### Could this AI be misused?

A pet care planner has low misuse potential, but a user could enter misleading pet data to receive advice for an edge case the knowledge base doesn't cover, which Claude might then fill with plausible-sounding but unverified information. The system mitigates this through the RAG guardrail (Claude is instructed to state when documentation doesn't cover a topic) and the design decision to keep the knowledge base as the authoritative source rather than letting the model rely on training data alone.

### What surprised me during testing

The retriever's recall was higher than expected. Even queries like "daily medication pet" reliably surfaced the medication scheduling chunk from `general_care.txt`. What surprised me negatively was that queries for enrichment sometimes returned exercise content instead, because both chunks share high-frequency words like "daily," "time," and "pet." This confirmed that precision (not just recall) requires better retrieval.

### AI collaboration

**Helpful suggestion:** When designing the logging architecture, Claude suggested using a module-level list rather than Streamlit session state for the in-app log accumulator, with the reasoning that session state is reset on certain reruns while a module-level variable persists for the server process lifetime. This was the correct approach and I used it directly.

**Flawed suggestion:** Claude initially suggested using `scikit-learn`'s `TfidfVectorizer` for the retriever. While technically correct, this would have added a heavy ML dependency (numpy, scipy, scikit-learn) for a problem that simple word-frequency counting solves adequately. I replaced it with the pure-Python `Counter`-based approach in `rag/retriever.py`, which keeps the setup lightweight and reproducible without sacrificing meaningfully on retrieval quality at this scale.
