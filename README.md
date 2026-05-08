# Phosphor

Phosphor is a mainframe security assessment automation tool for TN3270 green-screen applications. It drives IBM x3270/s3270 terminal sessions to perform enumeration, authentication testing, and application code discovery against z/OS CICS-based environments — tasks that are taken for granted in web testing but painful to do manually on a mainframe.

Named after the phosphor-coated CRTs that gave old terminal screens their green glow.

> **For authorized use only. Only run this tool against systems you have explicit written permission to test.**

---

**Note:** This project was originally developed in 2019 and kept private across two separate repos. It is being released here as a fresh extraction — the git history has been intentionally omitted to ensure no client-specific or sensitive data leaks from the original repos. The code has been cleaned up and ported to Python 3 with the assistance of [Claude Code](https://claude.ai/code) (Anthropic), which helped audit for sensitive data, refactor hardcoded client-specific values into XML config, fix several bugs, and add a test suite.

Because of the fresh-start approach, there may be rough edges or environment-specific assumptions that weren't obvious without a live target to test against. If you run into issues, PRs are very welcome — the heavy lifting is done, but real-world testing will shake out the remaining corners.

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

- Python 3
- x3270 / s3270 binaries (see below)
- RabbitMQ (for parallel modes)

```
pip install -r requirements.txt
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

## Authors

- **Adam H (Incendiary)** — [github.com/incendiary](https://github.com/incendiary)

## Acknowledgements

Phosphor would not exist without the work of **Phil Young / Soldier of Fortran ([@mainframed767](https://twitter.com/mainframed767))**.

- The original [MFscreen](https://github.com/mainframed/MFscreen) tool is the direct ancestor of this project — the core approach of driving x3270 to interact with mainframe applications came from there.
- The **Ethical Mainframe Hacking** course (co-created by Phil Young and Chad Rikansrud, originally released as *Evil Mainframe*) provided an excellent grounding in mainframe security concepts and was attended during the development of this tool. The course has since been acquired by Broadcom — see the [announcement](https://news.broadcom.com/mainframe-software/broadcom-acquires-unique-mainframe-pentesting-class). If you are doing any mainframe security work, it is strongly recommended.
- His broader body of mainframe security research — talks, tools, and writeups — is an invaluable resource for anyone working in this space.

The CICS exception list (`cicsexceptions`) of transactions known to hang or crash CICS is also drawn from his public research.
