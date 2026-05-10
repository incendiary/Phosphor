# Phosphor

Phosphor is a mainframe security assessment automation tool for TN3270 green-screen applications. It drives IBM x3270/s3270 terminal sessions to perform enumeration, authentication testing, and application code discovery against z/OS CICS-based environments — tasks that are taken for granted in web testing but painful to do manually on a mainframe.

Named after the phosphor-coated CRTs that gave old terminal screens their green glow.

> **For authorized use only. Only run this tool against systems you have explicit written permission to test.**

---

## Background

This project started around 2015–2018 during a period of fairly regular mainframe and mid-range work — z/OS CICS environments, but also IBM i (iSeries / AS400) systems. Mainframe security testing is one of those areas where the underlying techniques are well understood but the tooling has always lagged far behind the web world. If you do web testing you reach for Burp and it handles the mechanics — repeating requests, fuzzing inputs, categorising responses — so you can focus on what the application is doing. On a mainframe you are manually tabbing through green screens, hand-crafting transaction codes, and writing down responses in a spreadsheet.

Phosphor is an attempt to automate that mechanical work: populate a queue with candidate values, spin up N terminal sessions, let them run, collect the results. It won't replace judgement about what the results mean, but it removes the tedium of generating them.

It started as a fairly rough Python 2 script and was kept private across a couple of private repos. I'm releasing it now — cleaned up and ported to Python 3 — in the hope it is useful to someone doing similar work. If you're doing mainframe security assessments and find rough edges or missing features for your environment, PRs are very welcome.

---

**Note:** The git history has been intentionally omitted from this public release to ensure no client-specific or sensitive data leaks from the original private repos. The Python 3 port, security audit, refactor, and pre-release cleanup were done with the assistance of [Claude Code](https://claude.ai/code) (Anthropic) — including auditing for hardcoded secrets, refactoring client-specific values into XML config, fixing several bugs, adding a test suite, and a full Karpathy-guided code quality review. The issues that review surfaced are tracked in the roadmap below.

---

Based on foundational work by [Soldier of Fortran (@mainframed767)](https://github.com/mainframed).

---

## What it does

- **User enumeration** — identify valid usernames via login screen response differences
- **CICS transaction fuzzing** — discover accessible CICS regions and transaction codes
- **Application code discovery** — brute-force 3-character application codes and categorise responses
- **Bulk authentication testing** — run multiple parallel sessions via RabbitMQ queues
- **Department/account scraping** — extract user and department information from accessible screens
- **CEMT transaction enumeration** — scrape transaction lists from the CICS master terminal
- **Password change automation** — reset test account passwords from a known daily default
- **Excel reporting** — export results into spreadsheets for reporting

---

## How it works

Phosphor wraps x3270/s3270 (IBM 3270 terminal emulators) to script green-screen interactions. It uses RabbitMQ as a work queue, so you can run multiple Phosphor instances simultaneously against the same target — one per terminal session your test environment permits.

```
for i in {1..10}; do
    python phosphor.py -t <host>:<port> -u <user> -p <password> -mq localhost -app True -v False -s 0.25
done
```

Results are saved as HTML screenshots to disk, categorised by response type, and optionally written to an Excel workbook.

---

## Requirements

- Python 3.9+
- x3270 / s3270 binaries (see below)
- RabbitMQ (for parallel modes)

**Install as a tool (recommended):**

```
pip install .
phosphor --help
```

This installs the `phosphor` command and all runtime dependencies. To also install dev tools (Black, isort, flake8, pre-commit):

```
pip install ".[dev]"
```

**Run directly without installing:**

```
pip install -r requirements.txt
python phosphor.py --help
```

---

## Configuration

Phosphor is driven by an XML config file (`default.xml` by default, override with `-cfg`). It defines:

- **Application response signatures** — strings Phosphor looks for to classify a screen
- **CICS error codes** — known CICS responses to categorise
- **Test accounts** — credentials for password reset mode
- **Environments** — if your app spans multiple regions or instances
- **Screen positions** — where login fields, menus, and response strings live

A sanitised template is provided. You will need to tune it for your target environment.

Sensitive configuration (e.g. environment-specific password logic) lives in `inc/private_includes.py`, which is gitignored. A stub with dummy defaults is provided in `inc/public_includes.py`.

---

## x3270 / s3270 binaries

Phosphor requires a patched build of [suite3270](https://x3270.miraheze.org/wiki/Main_Page) that removes field-protection checks, allowing it to interact with protected mainframe screen fields. The patch and build instructions are included — the recommended way to get the binaries is via the Docker build below.

---

## Docker

The Dockerfile performs a two-stage build: it compiles the patched x3270/s3270 binaries from source, then packages them with Phosphor into a runtime image.

**Build:**

```
docker build -t phosphor .
```

**Run** (headless, connecting to a RabbitMQ instance named `phosphor-mq`):

```
docker run --rm \
  --network host \
  phosphor \
  -t <host>:<port> \
  -u <user> \
  -p <password> \
  -mq localhost \
  -app True \
  -v False \
  -s 0.25
```

For parallel assessment, run multiple containers simultaneously — one per terminal session your target permits:

```
for i in $(seq 1 10); do
  docker run -d --network host \
    -v $(pwd)/default.xml:/app/default.xml \
    phosphor -t <host>:<port> -u <user> -p <password> -mq localhost -ba True -v False -s 0.25
done
```

> **Note:** Visible mode (`-v True`) requires an X11 server and mounting `/tmp/.X11-unix` into the container. Headless (`-v False`) is recommended for Docker use.

---

## RabbitMQ

Phosphor uses persistent RabbitMQ queues for parallel operation. The easiest way to run both RabbitMQ and Phosphor together is via docker-compose:

```
# Start RabbitMQ (stays up in background)
docker compose up rabbitmq -d

# Populate a queue
docker compose run --rm phosphor -t <host>:<port> -u <user> -p <pass> -mq rabbitmq -popu True

# Run 10 parallel assessment sessions
docker compose up --scale phosphor=10
```

Management UI: http://localhost:15672 (default creds: guest/guest)

To run RabbitMQ standalone without docker-compose:

```
docker run -d \
  --hostname phosphor-mq \
  --name phosphor-mq \
  --publish="5672:5672" \
  --publish="15672:15672" \
  rabbitmq:3-management
```

---

## Changelog

### v3.0.0 (2026-05-10)

**Refactor / code quality — closes #10–#16**
- Removed dead code: `print_countdown`, `cElementTree` try/except guard (removed in Python 3.9), all commented-out print/debug calls
- `cicsexceptions` deduplicated — single definition in `mq_includes.py`; `cics_mixin.py` now imports it
- Repeated connect → vtam_login → set_region → login_to_app sequence in `main()` extracted into `_connect_and_login()` helper — eliminates four near-identical blocks
- `AppMixin._bulk_prepend` property replaces four inline `prepend_string` builds; four identical MQ publish calls in `populate_mq_for_excel` collapsed into a loop
- Control flow: `for...else` removed from `search_for_*` functions; `manual_export` uses `with open()` and `logger.debug` instead of raw `open`/`print`; literal `.lower()` comparisons simplified
- All what-comments stripped from `mq_includes.py` and `public_includes.py`
- `pyproject.toml` version synced to `2.7.0`; Black `target-version` updated to match `requires-python = ">=3.9"` (py38 removed, py312 added)
- GitLeaks added as first hook in `.pre-commit-config.yaml`

Net: −210 lines, +45. All 74 tests pass; gitleaks, black, isort, flake8 clean.

---

### v2.7.0 (2026-05-09)

**Operations**
- GitHub Actions workflow (`docker-publish.yml`) builds the two-stage Phosphor image (patched x3270/s3270 compile + Python runtime) and pushes to `ghcr.io/incendiary/phosphor`
- Tagged releases push a semver tag (e.g. `v2.7.0`) and `major.minor`; pushes to `main` update `latest`
- GHA layer cache keeps repeat builds fast — the slow suite3270 compile stage is only rerun when the Dockerfile or patch changes

---

### v2.6.0 (2026-05-09)

**Features**
- SQLite results store (`inc/db.py`, `PhosphorDB`) — every scan result is now persisted to a local SQLite database alongside the existing MQ publish, enabling post-run analysis without draining queues
- `--db` CLI flag (default: `phosphor.db`) selects the database path; pass `:memory:` in tests
- All five result-producing mixins (`auth`, `cics`, `app`, `cemt`, `users`) write to the DB
- 6 new tests for `PhosphorDB`; `pytest` added to `requirements-dev.txt`; `.venv/` and `*.db` added to `.gitignore`

---

### v2.5.0 (2026-05-09)

**Refactor**
- Replaced the bespoke `screen()` / `bcolors` / `set_debug()` output system with Python's standard `logging` module
- All nine Python source files now use `logging.getLogger(__name__)`; output format is preserved via `_ColourFormatter` in `phosphor.py`
- Logging level is set globally by `_setup_logging(args.debug)` — DEBUG or INFO depending on the `-d` flag

---

### v2.4.0 (2026-05-09)

**Packaging**
- `pyproject.toml` extended with full project metadata, dependencies, and a `phosphor` CLI entry point — `pip install .` now installs Phosphor as a tool; `pip install ".[dev]"` also installs Black, isort, flake8, and pre-commit
- MIT `LICENSE` file added

---

### v2.3.0 (2026-05-09)

**Refactor**
- `phosphor.py` split into six focused modules — `phosphor.py` drops from 1270 to 438 lines; logic now lives in `inc/auth_mixin.py`, `inc/cics_mixin.py`, `inc/app_mixin.py`, `inc/users_mixin.py`, `inc/cemt_mixin.py`, and `inc/password_mixin.py`. `MainFrame` inherits from all six via Python mixins. No interface changes; all 68 tests pass.

---

### v2.2.0 (2026-05-09)

**Operations**
- GitHub Actions CI workflow — runs flake8, `black --check`, `isort --check`, and the full test suite on Python 3.9–3.12 for every push and pull request to main

---

### v2.1.0 (2026-05-09)

**Bug fixes**
- `login_to_app`: `self.d` typo — would NameError immediately on any overtype login
- `check_application`: double ack when a bad app code was encountered — pika would raise a channel exception on the second ack
- `check_application`: `application_response` and `mq_queue` were left as `None` for bad codes, causing a crash on the subsequent publish
- `assess_cics_screen`: `cics_unknown_wierd` misspelling meant results were published to a queue that was never declared — fixed to `cics_unknown_weird` throughout
- `check_cics_transactions` / `check_application` / `check_login`: `delivery_tag == 1` guard only fired for the very first message on a channel; subsequent outer loop iterations would drain the entire queue in one pass rather than processing one message at a time
- `search_for_previous_application_code`: off-by-one in `range(1, ws.max_row)` — the last row of the worksheet was always skipped
- `connect_to_zos`: bare `except:` swallowed `SystemExit` and `KeyboardInterrupt`
- `phosphor.py` top-level import: bare `except:` on the private-includes import replaced with `except ImportError:`

**New features**
- `docker-compose.yml`: RabbitMQ and Phosphor services wired together — healthcheck ensures Phosphor waits for the broker; `default.xml` is a bind-mount so config can be tuned per engagement without rebuilding; scales with `docker compose up --scale phosphor=N`

**Tests**
- 22 new tests covering: `make_and_set_folder_path`, `look_for_app_code`, `look_for_login_code`, `assess_login_screen`, `find_cemt_transactions_on_screen`, bad-code path in `check_application`, and the `search_for_previous_application_code` off-by-one regression
- Total: 68 tests (up from 46)

**Code quality**
- Black, isort, and flake8 applied across all Python files — zero violations
- pre-commit hooks enforce formatting and linting on every commit
- `requirements-dev.txt` added for contributor setup

---

### v2.0.0 (2026-05-09)

Python 3 port. See release notes on GitHub.

---

### v1.0.0

Initial public release. Python 2.

---

## Roadmap

The project works, but there are known areas for improvement. Contributions welcome.

**Code quality**
- [x] Split `phosphor.py` into focused modules (CICS, app testing, user enumeration, department scraping, CEMT, password reset)
- [x] Karpathy-guided codebase review — full review using the [Karpathy coding guidelines skill](https://github.com/forrestchang/andrej-karpathy-skills) to surface over-engineering, dead code, and unnecessary abstractions introduced during the port and refactor ([#9](https://github.com/incendiary/Phosphor/issues/9))
- [x] Remove dead code — `print_countdown`, dead `cElementTree` guard, commented-out print/debug calls ([#10](https://github.com/incendiary/Phosphor/issues/10))
- [x] Deduplicate `cicsexceptions` constant — defined identically in two modules; one should import from the other ([#11](https://github.com/incendiary/Phosphor/issues/11))
- [x] Extract repeated login sequence in `main()` — connect → vtam_login → set_region → login_to_app copy-pasted into four blocks ([#12](https://github.com/incendiary/Phosphor/issues/12))
- [x] Minor duplication fixes — `prepend_string` repeated 4× in `AppMixin`; four identical publish calls in `populate_mq_for_excel` ([#13](https://github.com/incendiary/Phosphor/issues/13))
- [x] Control flow fixes — `while...else`, literal `.lower()` calls, `manual_export` raw prints, missing `with open()` ([#14](https://github.com/incendiary/Phosphor/issues/14))
- [x] Remove what-comments from `mq_includes.py` and `public_includes.py` — describe what rather than why ([#15](https://github.com/incendiary/Phosphor/issues/15))
- [x] Fix `pyproject.toml` version field and `black` target-version to match `requires-python = ">=3.9"` ([#16](https://github.com/incendiary/Phosphor/issues/16))
- [ ] Integration-style tests against a known-good target — current tests mock the emulator; real target tests would catch screen parsing and timing regressions ([#8](https://github.com/incendiary/Phosphor/issues/8))

**Features**
- [x] Proper Python packaging (`pyproject.toml`) — `pip install .` installs a `phosphor` CLI command
- [x] Configurable logging — replace `screen()` with Python's `logging` module ([#5](https://github.com/incendiary/Phosphor/issues/5))
- [x] Results database — lightweight SQLite store for post-run analysis without draining MQ queues ([#6](https://github.com/incendiary/Phosphor/issues/6))

**Operations**
- [x] CI pipeline (GitHub Actions) running tests and linting on every push
- [x] Pre-built Docker image published to a registry ([#7](https://github.com/incendiary/Phosphor/issues/7))

If you hit a bug or missing feature on a real target, please open an issue or PR — that kind of feedback is the most valuable thing for a tool like this.

---

## Authors

- **Adam H (Incendiary)** — [github.com/incendiary](https://github.com/incendiary)

## Acknowledgements

Phosphor would not exist without the work of **Phil Young / Soldier of Fortran ([@mainframed767](https://twitter.com/mainframed767))**.

- The original [MFscreen](https://github.com/mainframed/MFscreen) tool is the direct ancestor of this project — the core approach of driving x3270 to interact with mainframe applications came from there.
- The **Ethical Mainframe Hacking** course (co-created by Phil Young and Chad Rikansrud, originally released as *Evil Mainframe*) provided an excellent grounding in mainframe security concepts and was attended during the development of this tool. The course has since been acquired by Broadcom — see the [announcement](https://news.broadcom.com/mainframe-software/broadcom-acquires-unique-mainframe-pentesting-class). If you are doing any mainframe security work, it is strongly recommended.
- His broader body of mainframe security research — talks, tools, and writeups — is an invaluable resource for anyone working in this space.

The CICS exception list (`cicsexceptions`) of transactions known to hang or crash CICS is also drawn from his public research.
