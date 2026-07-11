# PLAN.md

# YomiKata

> Native Japanese hover dictionary for Ubuntu using the Linux Accessibility (AT-SPI) framework.

---

# Project Overview

YomiKata is a native Linux desktop application inspired by the excellent **10ten Japanese Reader** browser extension.

Instead of running inside a browser, YomiKata works with native desktop applications by using the Linux Accessibility framework (AT-SPI).

When the user hovers over Japanese text inside supported applications, YomiKata should:

1. Detect the accessible text under the mouse.
2. Extract the surrounding sentence.
3. Tokenize the sentence.
4. Determine the hovered word.
5. Lookup dictionary information.
6. Display a lightweight popup beside the cursor.

The primary goal is to provide an experience comparable to browser hover dictionaries while remaining completely native.

---

# Scope

This project intentionally focuses on a single approach.

## Supported

- AT-SPI accessibility
- Native GTK applications
- Native Qt applications
- LibreOffice
- Gedit
- GNOME Text Editor
- Evince
- VSCode (when accessibility is available)

## Explicitly Out of Scope

- OCR
- Screen capture
- Browser extensions
- Thunderbird
- AI translation
- LLM explanations
- Grammar explanations
- Speech synthesis
- Flashcards
- Anki integration
- Wayland screen capture portals
- Windows/macOS support

These may become future projects after the core application is stable.

---

# Technical Requirements

## Language

Python 3.12+

## Package Manager

uv

## GUI

GTK4

Libadwaita

## Accessibility

AT-SPI2

pyatspi

## Tokenizer

SudachiPy

## Dictionary

JMdict

KANJIDIC2

SQLite

## Testing

pytest

## Code Quality

ruff

black

mypy

---

# Software Engineering Principles

The codebase should be designed as if it were a long-term open-source project.

Always prioritize:

- readability
- maintainability
- modularity
- testability

Avoid clever implementations.

Avoid premature optimization.

Avoid global state.

Every module should have a single responsibility.

Prefer composition over inheritance.

Use dependency injection whenever appropriate.

Every public function must have:

- type hints
- docstrings

Never use print().

Always use logging.

---

# High-Level Architecture

```
                 Mouse Hover
                      │
                      ▼
              Hover Monitor
                      │
                      ▼
          Accessibility Extractor
                 (AT-SPI)
                      │
                      ▼
            Sentence Extractor
                      │
                      ▼
              Sudachi Tokenizer
                      │
                      ▼
            Hover Token Resolver
                      │
                      ▼
            Dictionary Engine
          (JMdict / KANJIDIC2)
                      │
                      ▼
                Popup Renderer
```

Each stage should remain independent.

No module should know implementation details of another module.

---

# Project Structure

```
src/

    app.py

    hover/
        monitor.py
        debounce.py

    atspi/
        extractor.py
        cursor.py

    tokenizer/
        sudachi.py

    dictionary/
        backend.py
        sqlite.py
        jmdict.py
        kanjidic.py

    popup/
        window.py
        renderer.py

    util/
        cache.py
        japanese.py
        logging.py

tests/

assets/

database/
```

---

# Architecture Rules

## Hover Module

Responsible only for:

- monitoring mouse movement
- detecting hover
- debounce

Must NOT:

- access dictionary
- parse Japanese
- display popup

---

## AT-SPI Module

Responsible only for:

- locating accessible object
- extracting text
- retrieving offsets

Must gracefully handle unsupported applications.

Never crash.

---

## Sentence Module

Responsible only for:

- extracting the surrounding sentence

Must stop at:

- 。
- ！
- ？
- newline

---

## Tokenizer Module

Responsible only for:

- Sudachi tokenization

Must return:

- surface
- reading
- dictionary form
- POS
- start offset
- end offset

Offsets must exactly match the original sentence.

---

## Dictionary Module

Responsible only for dictionary lookup.

Must hide SQLite implementation behind an abstraction.

Future backends should be replaceable without changing callers.

---

## Popup Module

Responsible only for rendering.

Must never contain business logic.

Must never access dictionaries directly.

---

# Performance Targets

Hover polling

30 ms

Dictionary lookup

<5 ms

Popup rendering

<10 ms

Total latency

<50 ms

Memory

<150 MB

---

# Error Handling

The application should never crash when:

- accessibility is unavailable
- object disappears
- no text exists
- text is not Japanese
- dictionary lookup fails
- application closes

Failures should return Optional values or Result-like objects where appropriate.

---

# Milestone Development Strategy

The project should be developed incrementally.

Never generate the entire project in one step.

For every milestone:

1. Explain the design.
2. Explain why the design is chosen.
3. Mention alternative approaches.
4. Implement the code.
5. Write tests.
6. Summarize completed work.
7. Explain remaining work.

Favor iterative development over large code dumps.

---

# Milestone 1

Repository initialization

Deliverables

- uv project
- pyproject.toml
- directory layout
- Ruff
- Black
- MyPy
- pytest
- logging configuration
- GitHub-ready structure

---

# Milestone 2

Hover module

Implement

- HoverMonitor
- debounce logic
- hover events

No popup.

No dictionary.

Unit tests required.

---

# Milestone 3

AT-SPI module

Implement

AccessibilityExtractor

Responsibilities

- locate accessible object
- retrieve text
- retrieve offsets

Must gracefully fail.

Unit tests where possible.

---

# Milestone 4

Sentence extraction

Input

Japanese text

Offset

Return

- sentence
- sentence offset

Unit tests required.

---

# Milestone 5

Tokenizer

Implement Sudachi tokenizer.

Return

- surface
- reading
- lemma
- POS
- offsets

Unit tests required.

---

# Milestone 6

Hover token resolution

Given

- sentence
- offsets
- tokens

Return

Hovered token.

Unit tests required.

---

# Milestone 7

Dictionary backend

Create abstraction layer.

Implement SQLite backend.

Import JMdict.

Fast lookup.

Unit tests required.

---

# Milestone 8

KANJIDIC integration

Return

- On reading
- Kun reading
- meanings
- grade
- stroke count
- JLPT

---

# Milestone 9

Popup UI

GTK4 popup

Requirements

- always on top
- never steals focus
- follows cursor
- lightweight
- fade in/out

---

# Milestone 10

Integration

Connect

Hover

↓

AT-SPI

↓

Sentence

↓

Tokenizer

↓

Dictionary

↓

Popup

Optimize performance.

---

# Testing Requirements

pytest

Coverage should include

- tokenizer
- sentence extraction
- dictionary lookup
- offset mapping
- hover resolution

Integration tests

- Gedit
- LibreOffice
- GTK TextView
- Qt TextEdit

---

# Coding Standards

Use

- dataclasses
- pathlib
- enums
- Protocol where appropriate
- dependency injection
- immutable objects when practical

Avoid

- singleton
- global variables
- God classes
- hidden side effects
- circular dependencies

---

# Instructions for Claude Sonnet

When implementing this project:

- Think like a senior Python software engineer.
- Explain design decisions before writing code.
- Prefer maintainability over cleverness.
- Keep modules small and focused.
- Never combine unrelated responsibilities.
- Use SOLID principles where appropriate.
- Ask questions instead of making assumptions about Linux accessibility APIs.
- Do not generate the entire application in one response.
- Implement milestone by milestone.
- After each milestone:
  - summarize what was completed,
  - explain remaining work,
  - wait for feedback before continuing.

The resulting repository should be suitable for long-term open-source maintenance and contributions.