# Roadmap

Where the project stands. Update after each milestone (see CLAUDE.md, Documentation).
Last updated: 2026-11-18 · branch `fix/ui-styling` · Alembic head `a9d742709640`

Legend: [x] finished · [~] in progress · [ ] not started

## Now / Next up
- **Now:** UI styling fixes + README screenshots (`fix/ui-styling`): awaiting PR
- **Next up:** Step 13, Celery + Redis
- **Then:** frontend follow-ups (streaming answers, answer feedback)

## Done
- [x] Ingestion: PDFs → chunks → embeddings → Chroma (843 chunks, 2 documents) · tag `phase-1-complete`
- [x] Hybrid retrieval: vector + BM25 → RRF → Cohere rerank, with RRF fallback · tag `phase-1-complete`
- [x] Generation with `[Source N]` citations, YAML prompt v1.0, `validate_citation` · tag `phase-2-complete`
- [x] Query logging, `GET /history` dashboard · tag `phase-2-complete`
- [x] Cleanup: key revoked and purged from git history, `.env` restored, `.gitignore` fixed (reported done by you)
- [x] Remote: private GitHub repo, phase tags, old branches removed
- [x] Dependencies: hand-written `requirements.txt` / `requirements-dev.txt` · PR #1
- [x] Schema: retrieval trace on `query_logs`, `eval_runs` + `eval_results`, first real Alembic migration, verified live · PR #2
- [x] `ragas` import fix: `langchain-community` pinned `<0.4` · PR #3
- [x] Docs: `docs/architecture.md`, `docs/ROADMAP.md`, CLAUDE.md update · PR #4
- [x] Study notes: `docs/record_notes.md` + keep-updated rule in CLAUDE.md · PR #5
- [x] Lint cleanup: `ruff check .` clean · PR #6
- [x] Step 8, offline unit tests (RRF, citations, stats, Cohere fallback, `/query` resilience) · PR #7
- [x] Step 9, eval: runner (custom metrics + RAGAS, threshold gate), 40-question gold set v1.3, baseline × 3, thresholds set · PR #8
- [x] Step 10, Docker + CI: GitHub Actions (ruff, migration round trip on Postgres 17, pytest, `docker build`), non-root `Dockerfile`, `docker-compose.yml` (API + own Postgres on 127.0.0.1:5433) · PR #9
- [x] Step 11, eval fixes: (1) citation ranges · PR #10, (2) prompt v1.2 for superseded guidance (q027) · PR #11, (3) source diversity after rerank + `source_coverage` metric, eval run 10 · PR #12
- [x] Step 12, Streamlit frontend: Ask page (citation badges, source cards, citation summary, examples, sidebar), History dashboard, `Dockerfile.frontend` + compose `ui` service on 127.0.0.1:8501, README · PR #13

## Remaining (in order)
- [ ] **Step 13, Celery + Redis**
- [ ] **Later** — frontend follow-ups: streaming answers, answer feedback (needs a route and a table), multi-turn query rewriting (a retrieval change, must pass the eval), an eval-runs page

## Open issues
- q033 (both documents already retrieved) still scores faithfulness 0.33–0.50; not a diversity problem, cause not yet diagnosed.
- The diversity floor (0.3) is absolute, but rerank scores are query-relative, so the swap also fires on 9 of 30 single-document questions. No metric dropped, but it costs those questions their 5th slot. A relative floor (share of the top score) is the likely refinement.
- `answer_relevancy` scores correct, concise answers as low as 0.56, so it is measured but not gated (`null`).
- CI cannot run the eval (PDFs and Chroma are not in git; needs paid keys). Run it locally and paste scores in the PR.
- `/history` and `/ingest` have no authentication.
- The UI's right-aligned question cards rely on a Streamlit `data-testid` selector in `frontend/style.css`; re-check after Streamlit upgrades.
- BM25 cache is keyed on chunk count; `load_prompt()` is cached: restart after re-ingesting or editing the prompt.
- `temperature=0` is not deterministic, but only the RAGAS judge scores varied across baseline runs (±0.01); retrieval and citation metrics were identical.

## How to update
After a milestone: move the item to Done with its PR or tag, refresh Now / Next up, update the date line.
