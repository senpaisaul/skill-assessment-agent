# Submission checklist — Deccan AI hackathon

**Deadline: Mon Apr 27, 2026, 1:00 AM IST**

---

## Required submission artifacts

- [ ] **Working prototype**
    - [x] Local setup documented in [README.md](README.md#local-setup)
    - [ ] Deployed URL — *to be added: backend on Render, frontend on Vercel*
- [ ] **Public repo with README**
    - [x] [README.md](README.md) — overview, architecture, scoring/logic, local setup
    - [x] [samples/README.md](samples/README.md) — sample inputs and how to run them
    - [x] [DEMO_SCRIPT.md](DEMO_SCRIPT.md) — 4-minute walkthrough script
- [ ] **3-5 minute demo video**
    - [x] Script ready at [DEMO_SCRIPT.md](DEMO_SCRIPT.md)
    - [ ] Recorded
    - [ ] Uploaded to YouTube/Loom (unlisted is fine)
- [x] **Architecture diagram + scoring/logic description**
    - [x] [Mermaid diagram in README](README.md#architecture)
    - [x] [Scoring & logic section in README](README.md#scoring--logic)
- [x] **Sample inputs and outputs** — three cases in [`samples/`](samples/) covering mixed/heavy-gap/no-gap branches

## Submission form fields

- [ ] Git repository URL — *to be added*
- [ ] Git username — `senpaisaul`
- [ ] Project documentation / README — link to `README.md`
- [ ] Demo video link — *to be added after recording*
- [ ] Project site URL — *to be added after deploy*

## Repository access

- [ ] **Add `hackathon@deccan.ai` as a collaborator on the GitHub repo before submitting** (per the hackathon instructions)

---

## Pre-submission smoke test

Run before recording the demo and before submitting:

```bash
cd backend && python tests/smoke_stage2.py && python tests/smoke_stage3.py && \
  python tests/smoke_stage4.py && python tests/smoke_stage5.py
```

All four should print `✅ STAGE N SMOKE TEST PASSED`. If any fail, do **not** submit until fixed.

```bash
cd frontend && npm run build
```

Should complete with no errors. (Build, not just typecheck — catches accidental client/server boundary issues that `tsc --noEmit` misses.)

## Pre-deploy checklist (if doing the deployed-URL option)

- [ ] Backend on Render
    - [ ] `OPENAI_API_KEY` set as env var
    - [ ] `LANGSMITH_TRACING=true` + `LANGSMITH_API_KEY` if you want traces
    - [ ] CORS origins updated to include the Vercel URL
    - [ ] Persistent disk attached for `checkpoints.sqlite` (otherwise sessions reset on every cold start)
- [ ] Frontend on Vercel
    - [ ] `NEXT_PUBLIC_BACKEND_URL` env var set to the Render URL
    - [ ] CVE-patched Next.js version (≥15.2.0)

## Day-of submission flow

1. Final smoke tests pass ✅
2. Demo video recorded + uploaded ✅
3. Both URLs live ✅
4. Push final commit, tag `v1.0`
5. Add `hackathon@deccan.ai` as repo collaborator
6. Fill in submission form
7. Confirm receipt
