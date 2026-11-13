#!/usr/bin/env python3
"""LIAS Unified CLI.

Interface for system diagnostics, automation execution, knowledge management,
and local routing.
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

# Ensure .claude is on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
CLAUDE_DIR = SCRIPT_DIR.parent
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

from lias.core.cache import CacheManager
from lias.core.config import LiasConfig
from lias.core.diagnostics import LiasDiagnostics
from lias.core.policy import PolicyEngine
from lias.core.recovery import RecoveryManager
from lias.core.registry import AutomationRegistry
from lias.core.router import CapabilityRouter
from lias.core.runner import LocalRunner
from lias.database.connection import initialize_database
from lias.database.migrations import MigrationManager
from lias.knowledge.retrieval import KnowledgeRetrieval
from lias.knowledge.store import KnowledgeStore


def init_subsystems(project_root: Path | None = None):
    cfg = LiasConfig(project_root=project_root)
    schema_file = cfg.lias_dir / "database" / "schema.sql"
    if not schema_file.exists():
        # Bootstrap a new/relocated project from the schema shipped with LIAS.
        schema_file = SCRIPT_DIR / "database" / "schema.sql"
    initialize_database(cfg.db_path, schema_file)
    MigrationManager(cfg.db_path).apply_migrations()

    policy = PolicyEngine(
        project_root=cfg.project_root,
        allow_tier1_auto=cfg.get("security", {}).get("tier1_auto_exec", True),
        allow_tier2_auto=cfg.get("security", {}).get("tier2_auto_exec", False),
    )
    registry = AutomationRegistry(manifests_dir=cfg.manifests_dir, db_path=cfg.db_path)
    cache_cfg = cfg.get("cache", {})
    cache = CacheManager(
        db_path=cfg.db_path,
        enabled=cache_cfg.get("enabled", True),
        default_ttl=cache_cfg.get("default_ttl_seconds", 3600),
        max_entries=cache_cfg.get("max_cache_entries", 1000),
    )
    runner = LocalRunner(
        project_root=cfg.project_root,
        registry=registry,
        policy=policy,
        db_path=cfg.db_path,
        max_output_bytes=cfg.get("runner", {}).get("max_output_bytes", 100000),
        cache=cache,
    )
    store = KnowledgeStore(
        db_path=cfg.db_path,
        project_id=cfg.get("project_name", "RobinLabs"),
        project_root=cfg.project_root,
    )
    retrieval = KnowledgeRetrieval(db_path=cfg.db_path)
    retrieval_cfg = cfg.get("retrieval", {})
    router = CapabilityRouter(
        registry=registry,
        runner=runner,
        retrieval=retrieval,
        max_results=retrieval_cfg.get("max_results", 5),
        max_context_chars=retrieval_cfg.get("max_context_chars", 4000),
        min_relevance_score=retrieval_cfg.get("min_relevance_score", 0.2),
        project_id=cfg.get("project_name", "RobinLabs"),
    )
    recovery = RecoveryManager(cfg, registry)
    diag = LiasDiagnostics(config=cfg, registry=registry, recovery=recovery)

    return cfg, registry, runner, store, retrieval, router, diag, cache, recovery


def main():
    parser = argparse.ArgumentParser(description="LIAS Local Intelligence & Automation CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Doctor
    subparsers.add_parser("doctor", help="Run comprehensive system diagnostics")

    # Status
    subparsers.add_parser("status", help="Show compact runtime status")

    # Run automation
    run_parser = subparsers.add_parser("run", help="Run registered automation")
    run_parser.add_argument("automation_id", help="Automation ID to execute")
    run_parser.add_argument("--input", default="{}", help="Input payload as JSON string")

    # Knowledge
    k_parser = subparsers.add_parser("knowledge", help="Manage project knowledge")
    k_subs = k_parser.add_subparsers(dest="k_action", required=True)

    search_p = k_subs.add_parser("search", help="Search knowledge records")
    search_p.add_argument("query", help="Search query")
    search_p.add_argument("--limit", type=int, default=5, help="Max results")

    add_p = k_subs.add_parser("add", help="Add or update knowledge")
    add_p.add_argument("--category", required=True, help="Knowledge category")
    add_p.add_argument("--content", required=True, help="Knowledge fact/content")
    add_p.add_argument("--provenance", default="user-cli", help="Source of knowledge")
    add_p.add_argument("--confidence", type=float, default=1.0, help="Confidence 0.0-1.0")
    add_p.add_argument("--expires", default=None, help="ISO timestamp after which the record expires")
    add_p.add_argument("--force", action="store_true", help="Store despite a duplicate/contradiction warning")

    list_p = k_subs.add_parser("list", help="List knowledge records")
    list_p.add_argument("--category", default=None, help="Filter category")

    del_p = k_subs.add_parser("delete", help="Delete a knowledge record by id")
    del_p.add_argument("record_id", help="Knowledge record id")

    index_p = k_subs.add_parser("index", help="Index foundational facts and project docs")
    index_p.add_argument("--seed-only", action="store_true", help="Only index foundational facts")

    # Route
    route_p = subparsers.add_parser("route", help="Route natural-language intent")
    route_p.add_argument("query", help="User intent or natural-language request")

    # Backup / restore / integrity
    backup_p = subparsers.add_parser("backup", help="Create a verified database backup")
    backup_p.add_argument("--reason", default="manual", help="Short reason for the backup")

    restore_p = subparsers.add_parser("restore", help="Restore a LIAS backup")
    restore_p.add_argument("backup_path", help="Path to a backup inside .claude/lias/backups")

    subparsers.add_parser("fsck", help="Check database integrity and configuration")

    # Quarantine
    q_parser = subparsers.add_parser("quarantine", help="Inspect or release quarantined automations")
    q_subs = q_parser.add_subparsers(dest="q_action", required=True)
    q_subs.add_parser("list", help="List disabled/quarantined automations")
    q_release = q_subs.add_parser("release", help="Re-enable an automation and reset its failures")
    q_release.add_argument("automation_id", help="Automation ID to release")

    # Cache
    cache_parser = subparsers.add_parser("cache", help="Inspect or clear the local cache")
    c_subs = cache_parser.add_subparsers(dest="c_action", required=True)
    c_subs.add_parser("stats", help="Show cache statistics")
    c_subs.add_parser("purge", help="Remove expired cache entries")
    c_subs.add_parser("clear", help="Remove all cache entries")

    # Candidates
    cand_parser = subparsers.add_parser("candidates", help="Inspect learned candidates")
    cand_parser.add_argument("--status", default=None, help="Filter: observed|promoted|quarantined")

    # Learning / autonomous growth
    learn_parser = subparsers.add_parser("learn", help="Observe work and grow local automation")
    l_subs = learn_parser.add_subparsers(dest="l_action", required=True)
    scan_p = l_subs.add_parser("scan", help="Scan execution logs for repeated workflows")
    scan_p.add_argument("--min-runs", type=int, default=3, help="Runs required to record a candidate")
    note_p = l_subs.add_parser("note", help="Record an explicitly confirmed fact")
    note_p.add_argument("text", help="Text starting with Confirmed:/Rule:/Decision: etc.")
    promote_p = l_subs.add_parser("promote", help="Promote validated knowledge candidates")
    promote_p.add_argument("--min-frequency", type=int, default=None, help="Override promotion threshold")
    gen_p = l_subs.add_parser("generate", help="Generate automation for one candidate")
    gen_p.add_argument("candidate_id", help="Candidate id from 'candidates'")
    gen_p.add_argument("--template", default=None, choices=["directory-summary", "log-summary"])
    gen_all_p = l_subs.add_parser("generate-all", help="Generate for every eligible candidate")
    gen_all_p.add_argument("--template", default=None, choices=["directory-summary", "log-summary"])

    args = parser.parse_args()
    cfg, registry, runner, store, retrieval, router, diag, cache, recovery = init_subsystems()

    if args.command == "doctor":
        res = diag.run_doctor()
        print(json.dumps(res, indent=2))
    elif args.command == "status":
        res = diag.get_status_summary()
        print(json.dumps(res, indent=2))
    elif args.command == "run":
        try:
            in_data = json.loads(args.input)
        except Exception:
            in_data = {}
        res = runner.run(args.automation_id, input_data=in_data, caller="cli")
        print(json.dumps(res.to_dict(), indent=2))
    elif args.command == "knowledge":
        if args.k_action == "search":
            results = retrieval.search(args.query, max_results=args.limit)
            out = [r.to_dict() for r in results]
            print(json.dumps(out, indent=2))
        elif args.k_action == "add":
            from lias.knowledge.validation import KnowledgeValidator

            validation = KnowledgeValidator(store).validate_candidate(
                category=args.category, content=args.content, confidence=args.confidence
            )
            if not validation.is_valid and not args.force:
                print(json.dumps({
                    "status": validation.status,
                    "stored": False,
                    "reason": validation.reason,
                    "conflicting_record": (
                        validation.conflicting_record.id if validation.conflicting_record else None
                    ),
                }, indent=2))
                sys.exit(2)
            rec = store.add(
                category=args.category,
                content=args.content,
                provenance=args.provenance,
                confidence=args.confidence,
                expires_at=args.expires,
                on_secret="reject",
            )
            print(json.dumps({"status": "stored", "record": rec.to_dict()}, indent=2))
        elif args.k_action == "list":
            records = store.list_all(category=args.category)
            print(json.dumps([r.to_dict() for r in records], indent=2))
        elif args.k_action == "delete":
            print(json.dumps({"deleted": store.delete(args.record_id), "id": args.record_id}, indent=2))
        elif args.k_action == "index":
            from lias.knowledge.indexing import ProjectIndexer
            indexer = ProjectIndexer(store=store, project_root=cfg.project_root)
            seed_count = indexer.index_foundational()
            doc_count = 0
            if not args.seed_only:
                for md in [cfg.claude_dir / "CLAUDE.md", cfg.project_root / "docs" / "COLLECTION.md"]:
                    if md.exists():
                        doc_count += indexer.index_markdown_file(md)
            print(json.dumps({
                "status": "success",
                "foundational_facts_indexed": seed_count,
                "document_chunks_indexed": doc_count,
            }, indent=2))
    elif args.command == "route":
        resp = router.route(args.query)
        print(json.dumps({
            "action": resp.action_type,
            "summary": resp.summary,
            "duration_ms": resp.duration_ms,
            "result_chars": resp.result_chars,
            "data": resp.data,
        }, indent=2))
    elif args.command == "backup":
        path = recovery.backup(args.reason)
        print(json.dumps({"status": "success", "backup": str(path)}, indent=2))
    elif args.command == "restore":
        safety = recovery.restore(Path(args.backup_path))
        print(json.dumps({
            "status": "success",
            "restored_from": args.backup_path,
            "safety_backup": str(safety),
        }, indent=2))
    elif args.command == "fsck":
        print(json.dumps(recovery.self_check(), indent=2))
    elif args.command == "quarantine":
        if args.q_action == "list":
            print(json.dumps(recovery.quarantined(), indent=2))
        elif args.q_action == "release":
            released = recovery.release(args.automation_id)
            print(json.dumps({"released": released, "automation_id": args.automation_id}, indent=2))
            if not released:
                sys.exit(2)
    elif args.command == "cache":
        if args.c_action == "stats":
            print(json.dumps(cache.stats(), indent=2))
        elif args.c_action == "purge":
            print(json.dumps({"purged": cache.purge_expired()}, indent=2))
        elif args.c_action == "clear":
            print(json.dumps({"cleared": cache.clear()}, indent=2))
    elif args.command == "learn":
        from lias.learning.candidates import CandidateManager
        from lias.learning.generator import AutomationGenerator
        from lias.learning.observer import WorkflowObserver
        from lias.learning.patterns import WORKFLOW_CATEGORIES

        manager = CandidateManager(cfg.db_path, store)
        observer = WorkflowObserver(manager)
        generator = AutomationGenerator(cfg, registry, manager)
        threshold = args.min_frequency if getattr(args, "min_frequency", None) is not None else cfg.get(
            "learning", {}
        ).get("promotion_frequency_threshold", 3)

        if args.l_action == "scan":
            observed = observer.observe_execution_log(cfg.db_path, min_runs=args.min_runs)
            print(json.dumps({
                "status": "success",
                "observed": [
                    {
                        "id": c.id,
                        "pattern": c.workflow_pattern,
                        "frequency": c.frequency,
                        "status": c.status,
                    }
                    for c in observed
                ],
            }, indent=2))
        elif args.l_action == "note":
            record = observer.observe_message(args.text)
            print(json.dumps({
                "status": "recorded" if record else "ignored",
                "candidate": None if not record else {
                    "id": record.id,
                    "pattern": record.workflow_pattern,
                    "frequency": record.frequency,
                    "category": record.metadata.get("category"),
                },
                "hint": None if record else "Prefix with Confirmed:, Rule:, Decision:, Architecture decision: or Known resolution:",
            }, indent=2))
        elif args.l_action == "promote":
            promoted = []
            for candidate in manager.list_candidates(status="observed"):
                if candidate.metadata.get("category") in WORKFLOW_CATEGORIES:
                    continue
                rec = manager.evaluate_and_promote(candidate.id, min_frequency=int(threshold))
                if rec:
                    promoted.append({"candidate_id": candidate.id, "knowledge_id": rec.id})
            print(json.dumps({"status": "success", "promoted": promoted}, indent=2))
        elif args.l_action == "generate":
            result = generator.generate(args.candidate_id, template=args.template)
            print(json.dumps(result.to_dict(), indent=2))
            if result.status not in ("generated", "reused"):
                sys.exit(2)
        elif args.l_action == "generate-all":
            results = []
            for candidate in manager.list_candidates(status="observed"):
                results.append(generator.generate(candidate.id, template=args.template).to_dict())
            print(json.dumps({"status": "success", "results": results}, indent=2))
    elif args.command == "candidates":
        from lias.learning.candidates import CandidateManager

        manager = CandidateManager(cfg.db_path, store)
        items = manager.list_candidates(status=args.status)
        print(json.dumps([
            {
                "id": c.id,
                "pattern": c.workflow_pattern,
                "frequency": c.frequency,
                "estimated_savings": c.estimated_savings,
                "risk_tier": c.risk_tier,
                "status": c.status,
                "metadata": c.metadata,
            }
            for c in items
        ], indent=2))


if __name__ == "__main__":
    main()
