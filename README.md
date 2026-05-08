# Phosphor

Phosphor is a mainframe security assessment automation tool for TN3270 green-screen applications. It drives IBM x3270/s3270 terminal sessions to perform enumeration, authentication testing, and application code discovery against z/OS CICS-based environments — tasks that are taken for granted in web testing but painful to do manually on a mainframe.

Named after the phosphor-coated CRTs that gave old terminal screens their green glow.

> **For authorized use only. Only run this tool against systems you have explicit written permission to test.**

---

**Note:** This project was originally developed in 2019 and kept private. It is now being released publicly after a cleanup pass assisted by [Claude Code](https://claude.ai/code) (Anthropic), which helped audit for sensitive data, refactor hardcoded client-specific values into XML config, and add an initial test suite. The code was written for Python 2 and may need work before it runs cleanly on modern systems — a Python 3 port and Docker update are on the to-do list. Contributions welcome.

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

Phosphor requires patched x3270/s3270 binaries that allow interaction with protected fields. Pre-built binaries for macOS and Linux are included. To build from source, see the Dockerfile.

---

## RabbitMQ

Phosphor uses persistent RabbitMQ queues for parallel operation. Quick setup with Docker:

```
docker volume create phosphor_log
docker volume create phosphor_data

docker run -d \
  -v "phosphor_log:/var/log/rabbitmq" \
  -v "phosphor_data:/var/lib/rabbitmq" \
  --hostname phosphor-mq \
  --name phosphor-mq \
  --publish="5672:5672" \
  --publish="15672:15672" \
  rabbitmq:3-management
```

Management UI: http://localhost:15672 (default creds: guest/guest)

---

## Authors

- **Adam H (Incendiary)** — [github.com/incendiary](https://github.com/incendiary)

## Acknowledgements

Phosphor would not exist without the work of **Phil Young / Soldier of Fortran ([@mainframed767](https://twitter.com/mainframed767))**.

- The original [MFscreen](https://github.com/mainframed/MFscreen) tool is the direct ancestor of this project — the core approach of driving x3270 to interact with mainframe applications came from there.
- The **Ethical Mainframe Hacking** course (co-created by Phil Young and Chad Rikansrud, originally released as *Evil Mainframe*) provided an excellent grounding in mainframe security concepts and was attended during the development of this tool. The course has since been acquired by Broadcom — see the [announcement](https://news.broadcom.com/mainframe-software/broadcom-acquires-unique-mainframe-pentesting-class). If you are doing any mainframe security work, it is strongly recommended.
- His broader body of mainframe security research — talks, tools, and writeups — is an invaluable resource for anyone working in this space.

The CICS exception list (`cicsexceptions`) of transactions known to hang or crash CICS is also drawn from his public research.
