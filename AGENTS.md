# AGENTS.md

Pattern Auto-Edit Tool (EditPat) edits ATP pattern files for DSSC/CMEM/HRAM.
Two UIs share one engine: `PAE.py` (Tkinter) and `PAE_webapp.py` (Streamlit),
both calling `src/main.py`.

## Commands

Run from the repo root with Python 3.11:

```bash
python PAE.py                       # desktop app
streamlit run PAE_webapp.py         # web app
python test/config_checks.py        # main checks; run after engine changes
python test/parallel_smoke.py       # manual multiprocess smoke test
```

No pytest, linter, or formatter is configured; run the scripts directly.
`test/data_editer_test.py` and `test/data_test_2.py` are Streamlit scratch
files, not tests.

## Rules

**Think first.** State your assumptions. Ask when the request has more than one
reasonable reading. If a simpler approach exists, say so before coding.

**Simplicity First.** Write the smallest change that solves the task. Use one
concrete implementation until a second caller needs the abstraction. Add
options, configurability, and fallbacks when the task asks for them. Add a
dependency only when the standard library cannot do the job, and ask first.

**Surgical Changes.** Touch only the lines the task needs. Match the
surrounding style. Clean up only what your own edit left unused; report
unrelated dead code instead of deleting it. Every changed line should trace
back to the request.

**Verify.** Run `python test/config_checks.py` after engine changes and say
what you ran. If a change has no automated check, describe how you verified it.

## Project facts

- `version` is defined in `PAE.py`; `PAE_webapp.py` imports it. Bump it once.
- The engine writes `Output/` relative to the current working directory and
  leaves temp files next to the source ATP. Tests copy `Sample/` into a temp
  directory; keep that pattern.
- One CSV row is one operation. Rows sharing a `Pattern` form a chain applied
  top to bottom. `README.md` is the source of truth for the format.
- `Sample/` fixtures and the CSV format are user-facing contracts: ask before
  changing either.
- Treat `.streamlit/secrets.toml` as local-only; keep it out of commits and do
  not print its contents.

## Communication

Use plain language: short sentences, everyday words. Define a term the first
time you use it, and explain why before how.
