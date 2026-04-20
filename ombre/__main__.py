"""
Ombre CLI entrypoint.
python -m ombre --help
python -m ombre serve --port 8080
python -m ombre run "Your prompt here"
python -m ombre stats
python -m ombre audit export --format json --output audit.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="ombre",
        description="Ombre — The infrastructure layer that makes AI trustworthy.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ombre run "Summarize this document"
  ombre serve --port 8080
  ombre stats
  ombre audit export --format json --output audit.json

Environment variables:
  OPENAI_API_KEY      OpenAI API key
  ANTHROPIC_API_KEY   Anthropic API key
  GROQ_API_KEY        Groq API key
  OMBRE_API_KEY       Ombre enterprise license key

Contact: ombreaiq@gmail.com
Docs:    https://docs.ombre-ai.com
GitHub:  https://github.com/ombre-ai/ombre-core
        """,
    )

    subparsers = parser.add_subparsers(dest="command")

    # serve command
    serve_parser = subparsers.add_parser("serve", help="Start self-hosted REST server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")

    # run command
    run_parser = subparsers.add_parser("run", help="Run a single prompt")
    run_parser.add_argument("prompt", help="Prompt to run")
    run_parser.add_argument("--model", default="auto", help="Model to use (default: auto)")
    run_parser.add_argument("--system", help="System prompt")
    run_parser.add_argument("--json", action="store_true", help="Output full JSON response")

    # stats command
    subparsers.add_parser("stats", help="Show pipeline statistics")

    # audit command
    audit_parser = subparsers.add_parser("audit", help="Audit log management")
    audit_sub = audit_parser.add_subparsers(dest="audit_command")
    export_parser = audit_sub.add_parser("export", help="Export audit logs")
    export_parser.add_argument("--format", choices=["json", "csv", "jsonl"], default="json")
    export_parser.add_argument("--output", default="ombre_audit.json", help="Output file path")

    # version
    subparsers.add_parser("version", help="Show version")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "version":
        from ombre import __version__
        print(f"Ombre v{__version__}")
        return

    # Build Ombre instance from environment variables
    from ombre import Ombre
    ai = Ombre(
        openai_key=os.environ.get("OPENAI_API_KEY"),
        anthropic_key=os.environ.get("ANTHROPIC_API_KEY"),
        groq_key=os.environ.get("GROQ_API_KEY"),
        mistral_key=os.environ.get("MISTRAL_API_KEY"),
        ombre_key=os.environ.get("OMBRE_API_KEY"),
    )

    if args.command == "serve":
        ai.serve(host=args.host, port=args.port)

    elif args.command == "run":
        response = ai.run(prompt=args.prompt, model=args.model, system=args.system)
        if args.json:
            print(response.to_json())
        else:
            print(response.text)
            print(f"\n[{response.summary}]")

    elif args.command == "stats":
        stats = ai.stats()
        print(json.dumps(stats, indent=2, default=str))

    elif args.command == "audit":
        if args.audit_command == "export":
            path = ai.export_audit(output_path=args.output, format=args.format)
            print(f"Audit exported to: {path}")
        else:
            audit_parser.print_help()


if __name__ == "__main__":
    main()
