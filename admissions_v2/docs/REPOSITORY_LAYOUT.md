# Repository Layout

All application code, tests, scripts, examples, skills and documentation live in
`admissions_v2/`. Run Python and npm commands from that directory, or from its
`frontend/` directory as documented. The repository root retains the overview,
license, ownership statement, agent rules, local launcher and deployment entries.

## Deployment

- Docker: run `docker build .` from the repository root. The Dockerfile copies
  `admissions_v2/` into `/app`, so the container command remains unchanged.
- Railway: the existing root `railway.json` still selects that Dockerfile.
- Procfile and Nixpacks: commands explicitly enter `admissions_v2/`.
- Separate frontend hosting: set the project directory to `admissions_v2/frontend`.
- Tests: run `python -m pytest -q` from `admissions_v2/`.

## Existing Local Workspace

The relocation moved the existing runtime data and dependencies without rewriting
databases. Ignored root links named `data`, `runtime`, and `.venv` preserve stored
absolute PDF paths and installed Python script paths. They are local compatibility
links, not duplicate copies and not GitHub contents. Do not delete them while old
source records or installed console scripts still reference these paths.

Fresh clones do not need these links: install dependencies and keep runtime data
inside `admissions_v2/` from the outset. Root `start_demo.command` delegates to the
application's existing launcher. The local demo credentials are unchanged.

## Student Interface Copy

Display admissions facts, relevant controls, missing values and useful operational
states. Do not display internal review procedures, self-reassurance slogans,
implementation limitations or generic claims about quality. Missing evidence page
metadata means there is no page shortcut, not a placeholder explanation on screen.
This presentation rule does not remove uncertainty from underlying records or
change the requirement for human confirmation before publication.
