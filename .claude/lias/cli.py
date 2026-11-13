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

from lias.core.config import LiasConfig
from lias.core.diagnostics import LiasDiagnostics
from lias.core.policy import PolicyEngine
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
    initialize_database(cfg.db_path, schema_file)
    MigrationManager(cfg.db_path).apply_migrations()

    policy = PolicyEngine(
        project_root=cfg.project_root,
        allow_tier1_auto=cfg.get("security", {}).get("tier1_auto_exec", True),
        allow_tier2_auto=cfg.get("security", {}).get("tier2_auto_exec", False),
    )
    registry = AutomationRegistry(manifests_dir=cfg.manifests_dir, db_path=cfg.db_path)
    runner = LocalRunner(
        project_root=cfg.project_root,
        registry=registry,
        policy=policy,
        db_path=cfg.db_path,
        max_output_bytes=cfg.get("runner", {}).get("max_output_bytes", 100000),
    )
    store = KnowledgeStore(db_path=cfg.db_path, project_id=cfg.get("project_name", "RobinLabs"))
    retrieval = KnowledgeRetrieval(db_path=cfg.db_path)
    router = CapabilityRouter(registry=registry, runner=runner, retrieval=retrieval)
    diag = LiasDiagnostics(config=cfg, registry=registry)

    return cfg, registry, runner, store, retrieval, router, diag


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

    list_p = k_subs.add_parser("list", help="List knowledge records")
    list_p.add_argument("--category", default=None, help="Filter category")

    index_p = k_subs.add_parser("index", help="Index foundational facts and project docs")
    index_p.add_argument("--seed-only", action="store_true", help="Only index foundational facts")

    # Route
    route_p = subparsers.add_parser("route", help="Route natural-language intent")
    route_p.add_argument("query", help="User intent or natural-language request")

    args = parser.parse_args()
    cfg, registry, runner, store, retrieval, router, diag = init_subsystems()

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
            rec = store.add(
                category=args.category,
                content=args.content,
                provenance=args.provenance,
                confidence=args.confidence,
            )
            print(json.dumps(rec.to_dict(), indent=2))
        elif args.k_action == "list":
            records = store.list_all(category=args.category)
            print(json.dumps([r.to_dict() for r in records], indent=2))
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
            "tokens_saved_estimate": resp.tokens_saved_estimate,
            "data": resp.data,
        }, indent=2))


if __name__ == "__main__":
    main()
