from __future__ import annotations

import json
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = WORKSPACE_ROOT / "evals" / "datasets" / "northstar_rag_v2.jsonl"
CORPUS_PATH = WORKSPACE_ROOT / "evals" / "datasets" / "northstar_rag_v2_corpus.jsonl"
PRIMARY_USER = "eval-user-primary"
SECONDARY_USER = "eval-user-secondary"


def note(note_id: str, created_at: str, note_type: str, raw_text: str, user_id: str = PRIMARY_USER) -> dict[str, str]:
    return {
        "note_id": note_id,
        "user_id": user_id,
        "created_at": created_at,
        "note_type": note_type,
        "raw_text": raw_text,
    }


def case(
    case_id: str,
    query: str,
    relevant_note_ids: list[str],
    expected_claims: list[dict[str, Any]],
    tags: list[str],
    expected_answer_behavior: str = "answer_with_sources",
    user_id: str = PRIMARY_USER,
) -> dict[str, Any]:
    return {
        "id": case_id,
        "dataset_version": "northstar_rag_v2",
        "user_id": user_id,
        "query": query,
        "relevant_note_ids": relevant_note_ids,
        "expected_claims": expected_claims,
        "expected_answer_behavior": expected_answer_behavior,
        "tags": tags,
    }


def claim(text: str, supporting_note_ids: list[str]) -> dict[str, Any]:
    return {"claim": text, "supporting_note_ids": supporting_note_ids}


def build_seed_examples() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    corpus = [
        note(
            "study-dsa-buy-sell-stock",
            "2026-07-18T20:15:00Z",
            "study_log",
            (
                "Completed the Buy & Sell Stock dynamic programming question for DSA practice. "
                "The implementation passed, but I marked it for revision because the state-transition reasoning still feels weak."
            ),
        ),
        note(
            "college-project-jun12-status",
            "2026-06-12T18:40:00Z",
            "project_update",
            (
                "College project update uploaded on 12 June: the build is almost done. "
                "Only a few specific details and the teacher's final review remain before submission."
            ),
        ),
        note(
            "retrieval-rrf-learn",
            "2026-07-03T09:10:00Z",
            "learning_plan",
            "Need to learn about RRF, especially how reciprocal rank fusion combines sparse and dense retrieval results.",
        ),
        note(
            "retrieval-rrf-complete",
            "2026-07-19T17:25:00Z",
            "learning_status",
            "Re ranking fusion completed: I finished the RRF notes, compared it with simple score averaging, and marked the topic done.",
        ),
        note(
            "aws-sqs-notes",
            "2026-07-21T11:00:00Z",
            "technical_note",
            (
                "AWS SQS notes: covered visibility timeout, dead-letter queues, long polling, and how worker retries interact with message deletion. "
                "No Lambda implementation status was recorded in this note."
            ),
        ),
        note(
            "geo-quiz-date",
            "2026-07-09T08:30:00Z",
            "academic_reminder",
            "Geography quiz is scheduled for the 22nd. Revise map symbols, monsoon winds, and Indian river basins before then.",
        ),
    ]

    cases = [
        case(
            "seed-dsa-revision-01",
            "Which coding questions do I still need to revise?",
            ["study-dsa-buy-sell-stock"],
            [claim("The Buy & Sell Stock DSA question was completed but still needs revision.", ["study-dsa-buy-sell-stock"])],
            ["semantic", "study", "revision", "seed"],
        ),
        case(
            "seed-college-project-01",
            "On July 25, where does my college project stand and when did I last update it?",
            ["college-project-jun12-status"],
            [
                claim("The college project was almost done, with only specifics and teacher review remaining.", ["college-project-jun12-status"]),
                claim("The last recorded update was uploaded on 12 June.", ["college-project-jun12-status"]),
            ],
            ["semantic", "chronology", "project-status", "seed"],
        ),
        case(
            "seed-rrf-status-01",
            "What is my RRF status?",
            ["retrieval-rrf-complete"],
            [claim("RRF was completed.", ["retrieval-rrf-complete"])],
            ["semantic", "status", "learning", "seed"],
        ),
        case(
            "seed-rrf-history-01",
            "Did I only plan to learn RRF or did I finish it?",
            ["retrieval-rrf-learn", "retrieval-rrf-complete"],
            [
                claim("There was an earlier plan to learn RRF.", ["retrieval-rrf-learn"]),
                claim("A later note says RRF was completed.", ["retrieval-rrf-complete"]),
            ],
            ["semantic", "chronology", "multi-note", "seed"],
        ),
        case(
            "seed-aws-lambda-no-context-01",
            "What is the status of my AWS Lambda work?",
            [],
            [],
            ["no-context", "near-miss", "aws", "seed"],
            expected_answer_behavior="abstain_or_request_clarification",
        ),
        case(
            "seed-geo-quiz-01",
            "When is my geo quiz?",
            ["geo-quiz-date"],
            [claim("The geography quiz is on the 22nd.", ["geo-quiz-date"])],
            ["semantic", "date-recall", "academic", "seed"],
        ),
    ]
    return cases, corpus


def build_dataset() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases, corpus = build_seed_examples()

    revision_items = [
        ("sliding-window-longest-substring", "Longest Substring Without Repeating Characters", "sliding window pointer movement"),
        ("graph-topological-sort", "Topological Sort", "cycle detection and indegree updates"),
        ("sql-window-functions", "SQL window functions", "partitioning and rank examples"),
        ("react-usememo", "React useMemo", "when memoization is actually useful"),
        ("system-design-cache", "cache invalidation notes", "write-through versus write-back tradeoffs"),
        ("probability-bayes", "Bayes theorem questions", "base-rate interpretation"),
        ("os-deadlock", "deadlock detection", "resource allocation graph examples"),
        ("networking-dns", "DNS resolution flow", "recursive resolver sequence"),
        ("db-indexing", "database indexing", "B-tree range scan behavior"),
        ("python-generators", "Python generators", "yield state and lazy iteration"),
        ("dp-knapsack", "0/1 knapsack DP", "space optimization"),
        ("ml-regularization", "regularization notes", "L1 versus L2 intuition"),
    ]
    for index, (slug, title, weak_area) in enumerate(revision_items, start=1):
        note_id = f"study-revise-{slug}"
        corpus.append(
            note(
                note_id,
                f"2026-07-{index + 1:02d}T19:00:00Z",
                "study_log",
                (
                    f"Completed {title} practice. Marked for revision because {weak_area} still needs another pass. "
                    f"The first attempt is done, but this should appear in my future revision queue."
                ),
            )
        )
        cases.append(
            case(
                f"semantic-revision-{index:02d}",
                f"What should I revise for {title.lower()}?",
                [note_id],
                [claim(f"{title} is complete but should be revised because {weak_area} needs another pass.", [note_id])],
                ["semantic", "study", "revision"],
            )
        )

    projects = [
        ("portfolio-site", "portfolio website", "2026-06-04", "layout is done; copy and deployment review remain"),
        ("robotics-demo", "robotics demo", "2026-06-08", "motion script works; calibration and mentor review remain"),
        ("college-project", "college project", "2026-06-12", "build is almost done; specifics and teacher review remain"),
        ("ml-mini-project", "ML mini project", "2026-06-16", "model is trained; evaluation table and guide feedback remain"),
        ("dbms-report", "DBMS report", "2026-06-20", "schema diagrams are done; normalization explanation remains"),
        ("mobile-prototype", "mobile prototype", "2026-06-24", "screens are wired; usability review remains"),
        ("iot-dashboard", "IoT dashboard", "2026-06-28", "device cards render; live sensor validation remains"),
        ("compiler-assignment", "compiler assignment", "2026-07-02", "parser works; error messages and TA review remain"),
        ("economics-presentation", "economics presentation", "2026-07-06", "slides are drafted; citation cleanup remains"),
        ("capstone-proposal", "capstone proposal", "2026-07-10", "problem statement is ready; advisor comments remain"),
    ]
    for index, (slug, title, date, status) in enumerate(projects, start=1):
        note_id = f"project-{slug}-status"
        corpus.append(
            note(
                note_id,
                f"{date}T18:40:00Z",
                "project_update",
                f"{title.title()} update uploaded on {date}: {status}. This is the latest recorded status for that project.",
            )
        )
        cases.append(
            case(
                f"semantic-project-status-{index:02d}",
                f"Where does my {title} stand and when did I last update it?",
                [note_id],
                [
                    claim(f"The {title} status is: {status}.", [note_id]),
                    claim(f"The last update was on {date}.", [note_id]),
                ],
                ["semantic", "chronology", "project-status"],
            )
        )

    topic_statuses = [
        ("rrf", "RRF", "need to learn how reciprocal rank fusion combines retrievers", "completed the RRF comparison and marked it done"),
        ("reranking", "reranking", "need to understand reranker scoring", "completed reranker notes and examples"),
        ("bm25", "BM25", "need to study lexical scoring and term saturation", "completed BM25 review with k1 and b notes"),
        ("vector-search", "vector search", "need to revise embedding similarity", "completed vector-search notes and distance examples"),
        ("prompt-caching", "prompt caching", "need to learn cache keys and invalidation", "completed prompt caching implementation notes"),
        ("sqs", "AWS SQS", "need to learn queue retries and DLQs", "completed SQS retry and dead-letter queue notes"),
        ("jwt-refresh", "JWT refresh flow", "need to understand refresh token rotation", "completed refresh-token rotation diagram"),
        ("chroma", "Chroma persistence", "need to test persistent collections", "completed Chroma persistence check"),
        ("fastapi-auth", "FastAPI auth", "need to review dependency guards", "completed FastAPI auth guard notes"),
        ("supabase-rls", "Supabase RLS", "need to learn row-level security policies", "completed RLS policy examples"),
    ]
    for index, (slug, title, plan, done) in enumerate(topic_statuses, start=1):
        plan_id = f"topic-{slug}-plan"
        done_id = f"topic-{slug}-done"
        corpus.extend(
            [
                note(plan_id, f"2026-07-{index:02d}T09:00:00Z", "learning_plan", f"Need to learn about {title}: {plan}."),
                note(done_id, f"2026-07-{index + 12:02d}T17:15:00Z", "learning_status", f"{title} status update: {done}."),
            ]
        )
        cases.append(
            case(
                f"semantic-topic-status-{index:02d}",
                f"What is my status on {title}?",
                [done_id],
                [claim(f"{title} is completed: {done}.", [done_id])],
                ["semantic", "status", "learning"],
            )
        )
        cases.append(
            case(
                f"semantic-topic-history-{index:02d}",
                f"Did I just plan {title} or finish it?",
                [plan_id, done_id],
                [claim(f"There was a plan to learn {title}, followed by a completion update.", [plan_id, done_id])],
                ["semantic", "chronology", "multi-note", "learning"],
            )
        )

    quizzes = [
        ("geography", "geo", "22nd", "map symbols and monsoon winds"),
        ("chemistry", "chem", "14th", "organic reactions"),
        ("history", "history", "18th", "freedom movement dates"),
        ("physics", "physics", "26th", "optics numericals"),
        ("maths", "math", "30th", "integration formulas"),
        ("english", "english", "11th", "poetry annotations"),
        ("economics", "eco", "24th", "market structures"),
        ("civics", "civics", "16th", "constitutional bodies"),
        ("biology", "bio", "28th", "genetics diagrams"),
        ("computer science", "cs", "20th", "SQL joins"),
    ]
    for index, (subject, shorthand, day, prep) in enumerate(quizzes, start=1):
        note_id = f"quiz-{subject.replace(' ', '-')}-date"
        corpus.append(
            note(
                note_id,
                f"2026-07-{index + 5:02d}T08:30:00Z",
                "academic_reminder",
                f"{subject.title()} quiz is scheduled for the {day}. Revise {prep} before the test.",
            )
        )
        cases.append(
            case(
                f"semantic-quiz-date-{index:02d}",
                f"When is my {shorthand} quiz?",
                [note_id],
                [claim(f"The {subject} quiz is on the {day}.", [note_id])],
                ["semantic", "date-recall", "academic"],
            )
        )

    near_miss_pairs = [
        ("aws-lambda", "AWS Lambda", "aws-sqs", "AWS SQS", "visibility timeout, dead-letter queues, and long polling"),
        ("docker-compose", "Docker Compose", "dockerfile", "Dockerfile", "base images, layers, and build cache"),
        ("kubernetes-ingress", "Kubernetes ingress", "kubernetes-pods", "Kubernetes pods", "pod restart policy and probes"),
        ("stripe-refunds", "Stripe refunds", "stripe-webhooks", "Stripe webhooks", "signature verification and retry handling"),
        ("vercel-env", "Vercel env vars", "vercel-deploy", "Vercel deploys", "preview deployments and build logs"),
        ("postgres-backups", "Postgres backups", "postgres-indexes", "Postgres indexes", "B-tree indexes and query plans"),
        ("redis-streams", "Redis streams", "redis-cache", "Redis cache", "TTL policies and cache invalidation"),
        ("oauth-consent", "OAuth consent screen", "jwt-refresh", "JWT refresh", "token rotation and expiry"),
        ("terraform-state", "Terraform state", "cloudformation", "CloudFormation", "stack updates and rollback events"),
        ("github-actions-secrets", "GitHub Actions secrets", "github-actions-cache", "GitHub Actions cache", "dependency caching"),
    ]
    for index, (missing_slug, missing_topic, existing_slug, existing_topic, existing_details) in enumerate(near_miss_pairs, start=1):
        corpus.append(
            note(
                f"near-miss-{existing_slug}",
                f"2026-07-{index + 15:02d}T10:45:00Z",
                "technical_note",
                f"{existing_topic} notes: covered {existing_details}. No status was recorded for {missing_topic}.",
            )
        )
        cases.append(
            case(
                f"semantic-no-context-near-miss-{index:02d}",
                f"What is the status of my {missing_topic} work?",
                [],
                [],
                ["no-context", "near-miss", "semantic"],
                expected_answer_behavior="abstain_or_request_clarification",
            )
        )

    daily_life_items = [
        ("passport-renewal", "passport renewal", "documents collected; appointment booking remains", "2026-07-04"),
        ("bike-service", "bike service", "oil change done; brake inspection remains", "2026-07-08"),
        ("bank-kyc", "bank KYC", "address proof uploaded; branch verification remains", "2026-07-12"),
        ("hostel-form", "hostel form", "form filled; warden signature remains", "2026-07-16"),
        ("library-dues", "library dues", "dues checked; receipt collection remains", "2026-07-20"),
        ("internship-application", "internship application", "resume sent; portfolio link update remains", "2026-07-24"),
        ("driving-license", "driving license", "test slot selected; payment confirmation remains", "2026-07-28"),
        ("scholarship-form", "scholarship form", "income certificate added; principal attestation remains", "2026-08-01"),
        ("lab-record", "lab record", "experiments written; observation table review remains", "2026-08-05"),
        ("club-event", "club event plan", "venue shortlisted; faculty approval remains", "2026-08-09"),
    ]
    for index, (slug, topic, status, date) in enumerate(daily_life_items, start=1):
        note_id = f"life-{slug}-status"
        corpus.append(note(note_id, f"{date}T15:30:00Z", "personal_task", f"{topic.title()} status: {status}. Last updated on {date}."))
        cases.append(
            case(
                f"semantic-life-status-{index:02d}",
                f"What is pending for my {topic}, and when did I update it?",
                [note_id],
                [claim(f"For {topic}, {status}; last updated on {date}.", [note_id])],
                ["semantic", "personal-task", "chronology"],
            )
        )

    isolation_topics = [
        ("DSA revision queue", "primary user needs to revise heaps and dynamic programming", "secondary user finished all revision"),
        ("college project review", "primary user is waiting on teacher review", "secondary user submitted a different project"),
        ("geography quiz", "primary user has quiz on the 22nd", "secondary user has quiz on the 12th"),
        ("AWS SQS notes", "primary user completed SQS retries", "secondary user is studying Lambda"),
        ("RRF status", "primary user completed RRF", "secondary user only planned RRF"),
    ]
    for index, (topic, primary_text, secondary_text) in enumerate(isolation_topics, start=1):
        primary_id = f"isolation-primary-semantic-{index:02d}"
        corpus.extend(
            [
                note(primary_id, f"2026-08-{index:02d}T12:00:00Z", "isolation_note", f"{topic}: {primary_text}."),
                note(
                    f"isolation-secondary-semantic-{index:02d}",
                    f"2026-08-{index:02d}T12:05:00Z",
                    "isolation_note",
                    f"{topic}: {secondary_text}. This belongs to another user.",
                    user_id=SECONDARY_USER,
                ),
            ]
        )
        cases.append(
            case(
                f"semantic-isolation-{index:02d}",
                f"What do my notes say about {topic}?",
                [primary_id],
                [claim(f"For {topic}, {primary_text}.", [primary_id])],
                ["semantic", "isolation"],
            )
        )

    latest_status_items = [
        ("resume-polish", "resume polish", "rough draft started", "final bullet cleanup completed"),
        ("mock-interview", "mock interview prep", "first practice was shaky", "second practice felt confident"),
        ("placement-aptitude", "placement aptitude prep", "quant section was pending", "quant drills completed"),
        ("open-source-pr", "open-source PR", "issue reproduced locally", "patch submitted for review"),
        ("hackathon-team", "hackathon team plan", "teammate search was open", "team of three confirmed"),
        ("dbms-viva", "DBMS viva prep", "ER diagrams were pending", "ER diagrams revised and ready"),
        ("mini-project-demo", "mini project demo", "demo script was incomplete", "demo script completed"),
        ("leetcode-streak", "LeetCode streak", "streak was at risk", "streak recovered with two problems"),
        ("teacher-feedback", "teacher feedback", "feedback was requested", "teacher asked for one final diagram"),
        ("lab-exam", "lab exam prep", "syntax practice was incomplete", "syntax practice completed"),
    ]
    for index, (slug, topic, old_status, new_status) in enumerate(latest_status_items, start=1):
        old_id = f"latest-{slug}-old"
        new_id = f"latest-{slug}-new"
        corpus.extend(
            [
                note(old_id, f"2026-06-{index + 2:02d}T10:00:00Z", "status_update", f"{topic.title()} earlier status: {old_status}."),
                note(new_id, f"2026-07-{index + 12:02d}T18:00:00Z", "status_update", f"{topic.title()} latest status: {new_status}."),
            ]
        )
        cases.append(
            case(
                f"semantic-latest-status-{index:02d}",
                f"What is the latest update on my {topic}?",
                [new_id],
                [claim(f"The latest update for {topic} is: {new_status}.", [new_id])],
                ["semantic", "chronology", "latest-status"],
            )
        )

    synonym_cases = [
        ("confidence-slump", "I felt underconfident after missing two easy array problems, so I wrote a note to rebuild basics calmly.", "What notes mention feeling low about easy coding mistakes?", "I felt underconfident after missing two easy array problems."),
        ("focus-sprint", "Started a focused two-hour study sprint for operating systems with phone notifications off.", "Where did I say I studied without distractions?", "I started a focused two-hour operating-systems study sprint with notifications off."),
        ("teacher-review", "Teacher review for the college project is the final external dependency before submission.", "Which note says someone else still has to check my college work?", "Teacher review is the final dependency before college project submission."),
        ("revision-backlog", "Created a backlog of weak topics: DP transitions, SQL partitions, and DNS recursion.", "What weak areas did I collect for later study?", "The weak-topic backlog includes DP transitions, SQL partitions, and DNS recursion."),
        ("exam-energy", "After the geography mock quiz I felt the map section was okay but river basins needed another pass.", "How did my map practice go and what geography part needs work?", "Map work was okay, but river basins needed another pass."),
        ("queue-learning", "SQS learning note: message visibility and DLQ behavior finally made sense after drawing the retry timeline.", "What queue concept clicked after I drew the retry flow?", "SQS message visibility and DLQ behavior made sense after drawing the retry timeline."),
        ("fusion-summary", "RRF takeaway: use reciprocal ranks when sparse and dense scores are not directly comparable.", "What was my takeaway about combining lexical and vector search?", "Use reciprocal ranks when sparse and dense scores are not directly comparable."),
    ]
    for index, (slug, text, query, answer) in enumerate(synonym_cases, start=1):
        note_id = f"synonym-{slug}"
        corpus.append(note(note_id, f"2026-07-{index + 20:02d}T13:10:00Z", "reflection", text))
        cases.append(
            case(
                f"semantic-synonym-{index:02d}",
                query,
                [note_id],
                [claim(answer, [note_id])],
                ["semantic", "paraphrase", "synonym"],
            )
        )

    distractors = [
        ("stocks", "Portfolio note: reviewed long-term investing, brokerage charges, and candlestick vocabulary, but no DSA revision task."),
        ("teacher", "Teacher meeting note: discussed attendance and lab batches, but not the college project status."),
        ("maps", "Map practice note: colored India outline maps for fun, unrelated to quiz scheduling."),
        ("aws", "AWS reading note: compared EC2 and S3 pricing, with no Lambda status update."),
        ("fusion", "Music playlist note: fusion tracks for study sessions, unrelated to retrieval algorithms."),
        ("revision", "General revision plan: revise lightly every Sunday, no specific completed question listed."),
        ("project", "Project ideas backlog: maybe build a finance dashboard later, no current status."),
        ("quiz", "Quiz app idea: build flashcards someday, unrelated to school exam dates."),
        ("rrf", "Search concepts glossary: mentions reciprocal, ranking, and fusion separately without a status update."),
        ("sqs", "Queue metaphor note: waiting in college canteen queue, unrelated to AWS."),
    ]
    for index in range(80):
        topic, text = distractors[index % len(distractors)]
        corpus.append(
            note(
                f"distractor-{index + 1:03d}-{topic}",
                f"2026-06-{(index % 28) + 1:02d}T{9 + (index % 8):02d}:20:00Z",
                "reference",
                f"Background {index + 1}: {text} This note is intentionally similar but not the answer.",
            )
        )

    if len(cases) != 100:
        raise ValueError(f"Expected 100 cases, built {len(cases)}")
    return cases, corpus


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record, separators=(",", ":")) for record in records) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    cases, corpus = build_dataset()
    write_jsonl(CASES_PATH, cases)
    write_jsonl(CORPUS_PATH, corpus)
    print(f"Wrote {len(cases)} cases to {CASES_PATH.relative_to(WORKSPACE_ROOT)}")
    print(f"Wrote {len(corpus)} notes to {CORPUS_PATH.relative_to(WORKSPACE_ROOT)}")


if __name__ == "__main__":
    main()
