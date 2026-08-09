# PRD - AI Work Memory (V1)

## Overview

AI Work Memory is a personal productivity and knowledge management system that converts unstructured work notes into structured organizational memory.

Users can quickly capture notes throughout the day. The system automatically extracts tasks, insights, questions, and actionable items using LLMs, stores them in a searchable knowledge base, and provides context-aware retrieval through a conversational interface.

The primary use case is helping knowledge workers quickly resume work after interruptions, weekends, or context switches.

---

# Problem Statement

Knowledge workers frequently lose context between work sessions.

Examples:

* Returning on Monday after working on multiple tasks Friday.
* Switching between projects throughout the week.
* Forgetting blockers, decisions, and next actions.
* Spending time reconstructing context from scattered notes.

Traditional note-taking tools store information but do not organize it into actionable knowledge.

---

# Goals

## Business Goal

Create a portfolio-quality AI application demonstrating:

* Event-driven architecture
* AWS serverless services
* LLM integration
* RAG architecture
* Vector search
* Knowledge extraction
* Modern React frontend

## User Goals

Users should be able to:

* Capture notes quickly
* View open tasks and pending questions
* Search previous work
* Resume interrupted work instantly
* Ask questions about previous work sessions

---

# Current State (Already Implemented)

## Note Ingestion

Frontend captures user notes.

## Event Pipeline

User Input
→ API
→ SQS
→ Lambda (Event Source Mapping)
→ Gemini API

## AI Processing

LLM extracts:

* Action Items
* Insights
* Questions
* Todos

## Storage

Supabase

Stores:

* Raw Notes
* Extracted Content

Chroma

Stores:

* Embeddings
* Semantic Search Index

---

# V1 Functional Requirements

## Feature 1 - Structured Knowledge Dashboard

Display extracted information.

### Sections

Open Tasks

Questions

Insights

Recent Notes

### User Actions

View

Filter

Sort

Search

---

## Feature 2 - Task Lifecycle Management

Tasks extracted by AI become first-class entities.

### Task Status

Open

In Progress

Completed

Archived

### User Actions

Mark Complete

Reopen

Delete

Edit Description

### Technical Requirement

Task updates should use direct database operations.

No LLM call required.

---

## Feature 3 - Source Traceability

Every extracted item must link to its originating note.

Example:

Task:
Verify VPC Configuration

Source:
Note #245
Created June 18 2026

### Benefits

Reduces hallucination

Improves explainability

Improves user trust

---

## Feature 4 - Entity Extraction

Extract relevant entities.

Examples:

AWS Lambda

SQS

React

PostgreSQL

Gemini

### Storage

Entity Table

Entity-Note Mapping Table

### Use Cases

Show all Lambda-related tasks

Show all notes mentioning SQS

Retrieve technology-specific work history

---

## Feature 5 - Conversational Work Memory

Chat interface over stored knowledge.

Example Questions:

"What am I currently blocked on?"

"What did I work on last Friday?"

"Show all unresolved AWS-related tasks."

"What decisions have I made recently?"

### Retrieval Flow

User Query

↓

Hybrid Search

* Structured SQL Retrieval
* Chroma Semantic Search

↓

Context Assembly

↓

LLM Response

---

## Feature 6 - Resume Work View

Primary V1 differentiator.

User clicks:

Resume My Work

System retrieves:

* Open Tasks
* Recent Notes
* Open Questions
* Recent Insights

LLM generates:

Current Focus Areas

Known Blockers

Recent Progress

Suggested Next Actions

---

# Non-Functional Requirements

## Performance

Task update < 500ms

Chat response < 5 seconds

Knowledge retrieval < 2 seconds

## Scalability

Asynchronous processing via SQS

Stateless Lambda workers

Independent retrieval services

## Reliability

Failed jobs sent to DLQ

Retry support

Logging and monitoring

---

# Architecture

React Frontend

↓

API Layer

↓

SQS

↓

Lambda Worker

↓

Gemini

↓

Knowledge Extraction

↓

Supabase

↓

Chroma

Chat Interface

↓

Retriever Service

↓

SQL + Vector Search

↓

Gemini

↓

Response

---

# Success Metrics

* User can resume work context within 30 seconds.
* Every task can be traced to a source note.
* Task completion does not require AI calls.
* Chat answers include source references.
* Retrieval accuracy sufficient to answer work-history questions.

---

# Resume Talking Points

Built an AI-powered Work Memory platform using React, AWS Lambda, SQS, Gemini, Supabase, and Chroma.

Designed an event-driven architecture for asynchronous note processing and knowledge extraction.

Implemented RAG-based retrieval combining structured SQL queries and vector similarity search.

Developed source-grounded AI responses to reduce hallucination and improve explainability.

Built task lifecycle management and contextual work-resumption workflows for knowledge workers.
