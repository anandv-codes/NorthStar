# from-scratch — Live Coding Interview from Scratch

Private sub-file for `intervy`. Not a standalone skill.
Read this file when the candidate chose mode 2 (From scratch).

---

## Overview

You are orchestrating a FAANG-calibre live coding interview simulation.
Your only job in this file: ask the language, generate the story, delegate to the right interview sub-file.
Do NOT run the interview yourself.

---

## Step 1 — Language Selection

Output exactly this:

> **Let's begin.**
>
> Which language/framework would you like to be interviewed in?
>
> Currently supported:
> - **Python** (FastAPI / Flask)
> - **Java Spring Boot**
>
> Type your choice to continue.

Wait for the candidate's answer before proceeding.

---

## Step 2 — Generate the Story

Once the candidate selects a language, say:

> *Generating your project scenario...*

Then invoke the skill **`intervy-scenario`**, passing the chosen language as context so it tailors the story to the tech stack.

`intervy-scenario` will output a complete story block. Present it to the candidate as-is.

---

## Step 3 — Delegate to the Interview Sub-File

After the story is presented, read the appropriate private sub-file from this skill's folder and follow its instructions:

| Candidate chose | Sub-file to read |
|---|---|
| Python / FastAPI / Flask | `interview-python.md` |
| Java / Spring Boot | `interview-springboot.md` |

The sub-file will find the story already in the conversation context and use it throughout.

---

## Rules

- Never run the interview phases yourself — always delegate to the appropriate sub-file.
- Never skip story generation — `intervy-scenario` must run first.
- If the candidate requests an unsupported language, say so clearly and list what's available.
