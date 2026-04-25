# Sample inputs and outputs

Three end-to-end test cases that exercise distinct paths through the agent:

| File | What it tests | Expected character |
|------|---------------|-------------------|
| `01_senior_ai_engineer.json` | Strong AI background applying to a senior platform role — Kubernetes is the headline gap | Mixed: 2-3 strengths, 2-3 gaps, full plan |
| `02_frontend_to_ml_pivot.json` | Frontend engineer pivoting to ML — most required skills are gaps | Plan-heavy: 4-6 modules, transferable-skill rationale |
| `03_strong_fit_minimal_gap.json` | Senior backend engineer applying to a senior backend role — already qualified | "You're a fit" path: empty plan, congratulatory summary |

## Running them

With the backend running at `localhost:8000`:

```bash
# Start a session
SESSION=$(jq -r '.input' samples/01_senior_ai_engineer.json | \
  curl -sX POST http://localhost:8000/api/assess/start \
    -H 'Content-Type: application/json' -d @- | \
  jq -r '.session_id')
echo "session: $SESSION"

# Answer questions interactively (the response body tells you the next question
# until interview_complete=true). For automated runs, write a small loop:
while true; do
  RESP=$(curl -sX POST http://localhost:8000/api/assess/respond \
    -H 'Content-Type: application/json' \
    -d "{\"session_id\":\"$SESSION\",\"response\":\"I have used this in production.\"}")
  COMPLETE=$(echo "$RESP" | jq -r '.interview_complete')
  [ "$COMPLETE" = "true" ] && break
  echo "next: $(echo "$RESP" | jq -r '.next_question.question')"
done

# Fetch the final result
curl -s http://localhost:8000/api/assess/result/$SESSION | jq
```

Or, easier: open `http://localhost:3000`, click **Load sample resume + JD**, and walk through it in the UI.

## Why these three

These cover the three distinct GapAnalyzer + PlanGenerator branches:

1. **Mixed** (sample 01) — the realistic case where the candidate has half the required skills. The IRT loop should ask harder questions on Python/LangGraph and easier ones on Kubernetes; the plan should put Kubernetes first with `Docker, Linux` as adjacent foundations.
2. **Heavy gaps** (sample 02) — pushes the planner to generate a long, prerequisite-ordered path. The reflection round should fire if the first plan misses Python (the foundation everything else depends on).
3. **No gaps** (sample 03) — exercises the early-return path in `plan_generator_node` that emits an empty plan with a congratulatory summary instead of forcing modules where none are needed.

Together they make a useful smoke set when iterating on the prompts.
