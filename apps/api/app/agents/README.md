# Multi-Agent AI System

The core intelligence layer of SmartMeal. A pipeline of specialist AI agents that collaborate to produce personalized, health-aware recommendations.

## System Overview

```
User Message
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│           MultiAgentOrchestrator                        │
│                                                      │
│  1. Sanitize input (prompt injection prevention)     │
│  2. Load UserMemory + Profile                        │
│  3. Fire Extractor (background, fire-and-forget)     │
│                                                      │
│  Phase 1 (sequential — others DEPEND on this):        │
│    HealthMonitor ──────────────────────────────────────┐
│                                                     ↓  │
│  Phase 2 (parallel):                            context │
│    NutritionAdvisor ◄──────────────────────────────┘   │
│    FitnessCoach    ◄──────────────────────────────┘   │
│    WebResearcher (optional, triggered by keywords)      │
│                                                      │
│  4. Check for clarification cards (priority-sorted)    │
│  5. Build synthesis context                           │
│  6. Final AI response (streamed via SSE)               │
└─────────────────────────────────────────────────────┘
```

## Why Two Phases?

NutritionAdvisor and FitnessCoach DEPEND on HealthMonitor output. HealthMonitor's output includes:

- `fitness_clearance`: list of exercises the user is cleared for, and a list to avoid
- `nutritional_needs.avoid`: foods to avoid today based on current health state
- `active_issues`: current health concerns that affect recommendations

If NutritionAdvisor or FitnessCoach ran before HealthMonitor completed, they might suggest foods or exercises that are contraindicated. Running HealthMonitor first ensures all subsequent recommendations are health-aware. This is a safety constraint, not a performance choice.

## Agents

### Agent 1: Extractor (`extractor_agent.py`)

**Role:** Silent data harvester — runs after every message.

**Trigger:** Every user message, fire-and-forget background task.

**Why background:** Must not block the SSE response stream. The user should receive AI text immediately without waiting for data extraction.

The extractor reads the user's message and conversation history to update the user's long-term memory. It is purely observational — it does not respond to the user.

What it extracts:

| Data | Destination | Merge Strategy |
|------|------------|----------------|
| Meals mentioned ("sáng nay ăn bánh mì") | `nutrition_memory.recent_meals` | Prepend + dedup by date+meal_type, max 30 |
| Body state ("mệt", "đau bụng") | `body_snapshot` | Deep-merge, additive for sore_areas |
| Health events ("bị tiêu chảy", "hết sốt rồi") | `health_events` | Prepend new, cap at 50 (newest first) |
| Stable facts ("tôi dị ứng hải sản") | `key_facts` | Upsert by exact text match |
| Fitness data ("hôm nay tập gym xong đau lưng") | `fitness_memory` | Deep-merge |

Severity mapping for body state:
- Vietnamese intensity words → numeric severity:
  - `hơi`, `nhẹ` → `mild`
  - `khá`, `vừa` → `moderate`
  - `rất`, `nặng` → `severe`

Conversation summary: rolling 800-token max, updated every 5+ messages. Maintains a concise gist of the conversation for context in future sessions.

### Agent 2: Health Monitor (`health_monitor_agent.py`)

**Role:** Medical-aware wellness assessor.

**Trigger:** Health keywords detected in message OR unresolved health events in user memory.

**Runs:** Phase 1 (sequential — must complete before Phase 2).

Key implementation details:

- **Rule-based urgent keyword check runs BEFORE the AI call.** Keywords like "đau ngực", "khó thở", "chóng mặt dữ dội" trigger urgent warnings immediately, without waiting for the AI model. This is a safety override.
- **Negation detection:** "không bị đau ngực" does NOT trigger the urgent warning. The sentence structure is checked.
- **Output structure:** The agent returns `fitness_clearance` (exercises to do/avoid), `nutritional_needs` (dietary adjustments), and `active_issues` (current concerns).

Output consumed by:
- `FitnessCoach`: reads `fitness_clearance` before any exercise recommendation
- `NutritionAdvisor`: reads `nutritional_needs.avoid` to filter suggestions
- `Orchestrator`: includes health status in synthesis context

### Agent 3: Nutrition Advisor (`nutrition_advisor_agent.py`)

**Role:** Certified nutritionist + Vietnamese cuisine expert.

**Trigger:** Nutrition/meal keywords in message ("ăn", "uống", "protein", "bữa sáng", etc.).

**Runs:** Phase 2 (parallel with FitnessCoach, after HealthMonitor).

Key implementation details:

- **Hard constraints:** Profile allergies and dietary restrictions are NEVER suggested. These are hard constraints that the AI must follow — no exceptions.
- **Soft constraints:** HealthMonitor's `nutritional_needs.avoid` items are de-prioritized today but not forbidden.
- **Post-processing safety check:** After the AI generates food suggestions, the code verifies none of the suggested foods contain allergens from the user's profile. If a conflict is found, that suggestion is removed.
- **Fallback:** If all suggestions are filtered (all foods have a conflict), the agent generates a safe generic meal ("canh rau mồng tơi với cơm trắng") that avoids all known allergens.
- **Deduplication:** Skips foods logged in `recent_meals` for the same date and meal_type. The user doesn't want to be told to eat the same thing twice in one day.

### Agent 4: Fitness Coach (`fitness_coach_agent.py`)

**Role:** Adaptive personal trainer with sports medicine knowledge.

**Trigger:** Fitness/workout keywords in message ("tập", "gym", "cardio", "yoga", "chạy bộ", etc.).

**Runs:** Phase 2 (parallel with NutritionAdvisor, after HealthMonitor).

Key implementation details:

- **MUST check `health_monitor.fitness_clearance` before any recommendation.** This is enforced by the orchestrator passing the clearance data in the agent's context.
- **Illness override:** If the user's health status is moderate or severe illness, the workout type is forced to `"rest"` and the exercises array is cleared. The AI recommends rest, stretching, or walking only.
- **Sore area detection:** If `body_snapshot.sore_areas` contains a body part, all exercises targeting that area are excluded. The agent suggests the antagonist muscle group instead (e.g., sore chest → suggest back exercises).
- **Safety override happens AFTER the AI call.** The AI proposes exercises, then the safety layer validates them against fitness_clearance. Any violations are removed or replaced.

### Agent 5: Web Researcher (`web_researcher_agent.py`)

**Role:** Evidence-based fact checker.

**Trigger:** Research keywords ("mới nhất", "nghiên cứu", "khoa học", "so sánh", "bằng chứng").

**Runs:** Phase 2 (optional, parallel with other agents).

Key implementation details:

- **Rate limited:** 3 searches per user per day, tracked in the `agent_runs` table.
- **Cache:** Results are cached per-user + per-query + per-day using a SHA256 hash of the query. Cached results are returned immediately without a web search.
- **Trusted sources:** Only 13 domains are allowed, including pubmed.gov, vinmec.com, healthline.com, who.int, nih.gov, and vietnamese health portals. All other domains are excluded.
- **Sanitization:** Web findings are sanitized before being injected into the synthesis context to prevent prompt injection via cached search results.

## UserMemory — The Agent Brain

The `UserMemory` model stores all persistent context about a user in PostgreSQL JSONB columns. One row per user.

```
user_memory
├── body_snapshot     Current physical state
│     ├── weight, energy_level, sleep_last_night
│     ├── digestion_status, muscle_status
│     └── sore_areas[], injury_areas[]
│
├── health_events[]  Append-only health log (max 50)
│     ├── event, severity, notes, resolved, extracted_at
│
├── nutrition_memory Eating patterns and restrictions
│     ├── recent_meals[]     last 30, dedup by date+meal_type
│     ├── foods_to_avoid[]  confirmed bad reactions
│     └── common_deficiencies[]
│
├── fitness_memory   Workout history and restrictions
│     ├── recent_workouts[], injury_history[]
│     └── preferences
│
├── key_facts[]      Stable personal facts (upserted by text)
│     └── fact, confidence, extracted_at
│
└── conversation_summary  Rolling 800-token session summary
```

## Memory Merge Strategy

Each field has a specific merge strategy:

| Field | Strategy | Why |
|-------|----------|-----|
| `body_snapshot` | Deep-merge | Preserves unrelated fields while updating specific ones |
| `sore_areas` | Additive union | Never removes soreness that the user reported — only adds |
| `health_events` | Prepend + cap at 50 | Newest events first; oldest pruned when full |
| `key_facts` | Upsert by exact text | Same fact ("dị ứng đậu phộng") updates confidence, doesn't duplicate |
| `recent_meals` | Prepend + dedup at 30 | Most recent first; no duplicate meal_type on same date |
| `nutrition_memory` | Deep-merge per sub-field | Per-field merge avoids overwriting unrelated data |
| `conversation_summary` | Replace if longer | Only update when there's new content to add |

## Orchestrator Synthesis

The `_build_synthesis_context` method assembles all agent outputs into a structured string injected into the final AI system prompt:

```
[HEALTH STATE]        ← from HealthMonitor
[NUTRITION GUIDANCE]  ← from NutritionAdvisor
[FITNESS GUIDANCE]    ← from FitnessCoach
[USER MEMORY]         ← body_snapshot, recent_meals, active issues
[DIETARY CONSTRAINTS] ← from profile + health conditions
```

This synthesis is then passed to `_stream_final_response`, which calls the AI model. The AI responds conversationally — it never exposes agent names or internal technical details to the user.

## Performance Characteristics

| Agent | Avg Latency | Max Tokens | Trigger Rate |
|-------|------------|------------|--------------|
| Extractor | ~800ms | 800 | 100% (background) |
| Health Monitor | ~1200ms | 800 | ~28% |
| Nutrition Advisor | ~1100ms | 800 | ~45% |
| Fitness Coach | ~950ms | 800 | ~18% |
| Web Researcher | ~3400ms | 800 | ~9% |
| Total (Phase 1+2) | ~2000ms | — | — |

Latency figures are estimates based on Groq API response times. Actual performance depends on network conditions and API load.

## Adding a New Agent

1. Create `apps/api/app/agents/your_agent.py` extending `BaseAgent`:

```python
from app.agents.base import BaseAgent, AgentResult

class YourAgent(BaseAgent):
    async def run(self, context: AgentContext, db: AsyncSession) -> AgentResult:
        # Implementation
        return AgentResult(...)
```

2. Import and add trigger keywords to `MultiAgentOrchestrator.__init__`:
```python
self.YOUR_KEYWORDS = ["keyword1", "keyword2"]
```

3. Add routing decision method:
```python
def _needs_your_agent(self, msg: str, memory) -> bool:
    return any(kw in msg for kw in self.YOUR_KEYWORDS)
```

4. Add to Phase 2 parallel task list in `process()`.

5. Update `_build_synthesis_context` to include your agent's output.

6. Write tests in `tests/test_your_agent.py`.

7. If the agent should run before or after another agent, adjust the phase assignment.
