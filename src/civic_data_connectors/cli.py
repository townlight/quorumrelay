"""JSON-only command boundary. Service and provider credentials are never request fields."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .models import OperationResult
from .transports.runtime import OPERATIONS, Principal, ServiceConfig, build_engine, execute, failure, load_config

EXIT_CODES = {"completed": 0, "partial": 2, "cancelled": 3, "failed": 4, "unsupported": 5}


def _read_path(name, root, limit):
    path = Path(name).resolve(strict=True)
    if root is not None and not path.is_relative_to(Path(root).resolve(strict=True)):
        raise ValueError("The requested local file is outside --file-root.")
    if not path.is_file():
        raise ValueError("The requested input must be a regular file.")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("The requested input exceeds its byte limit.")
    return data


def _emit(value, stream):
    stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n")
    stream.flush()


def main(argv=None, *, stdin=None, stdout=None, stderr=None, engine=None) -> int:
    stdin, stdout, stderr = stdin or sys.stdin, stdout or sys.stdout, stderr or sys.stderr
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="quorumrelay")
    parser.add_argument("operation", choices=(*OPERATIONS, "serve", "mcp"))
    parser.add_argument("--request", help="Explicit JSON/JSONL file; otherwise stdin")
    parser.add_argument("--jsonl", action="store_true")
    parser.add_argument("--content", help="Explicit saved capture file")
    parser.add_argument("--output", help="Export bytes to a new explicit file; stdout still carries JSON metadata")
    parser.add_argument("--file-root", help="Optional allowed local input root")
    parser.add_argument("--database", help="Application-owned optional SQLite state path")
    parser.add_argument("--config", help="Trusted service/principal configuration, never public request JSON")
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        if error.code:
            _emit(failure("invalid_cli", "Check CLI arguments and available commands.").public_dict(), stdout)
            return 64
        return 0
    owner = None
    try:
        config = load_config(args.config) if args.config else {}
        principal = Principal.from_dict(config.get("principal", {}))
        if args.operation == "serve":
            import uvicorn
            from .transports.http import create_app
            settings = ServiceConfig.from_dict(config.get("service", {}))
            app = create_app(engine or build_engine(database=args.database), settings)
            uvicorn.run(app, host=settings.host, port=settings.port, access_log=False)
            return 0
        if args.operation == "mcp":
            from .transports.mcp import run_stdio
            run_stdio(engine or build_engine(database=args.database), principal)
            return 0
        content = _read_path(args.content, args.file_root, 16 * 1024 * 1024) if args.content else None
        if args.output and (args.operation != "export" or args.jsonl):
            raise ValueError("--output requires a single export operation.")
        owner = engine or build_engine(database=args.database)
        if args.request:
            raw = _read_path(args.request, args.file_root, 24 * 1024 * 1024).decode("utf-8-sig")
            lines = raw.splitlines() if args.jsonl else [raw]
        elif args.jsonl:
            lines = iter(stdin)
        else:
            raw = stdin.read(24 * 1024 * 1024 + 1)
            if len(raw.encode("utf-8")) > 24 * 1024 * 1024:
                raise ValueError("The JSON request exceeds its byte limit.")
            lines = [raw]
        code = 0
        for line in lines:
            if not line.strip() and args.jsonl:
                continue
            framing_error = False
            try:
                if len(line.encode("utf-8")) > 24 * 1024 * 1024:
                    raise ValueError("The JSONL request exceeds its byte limit.")
                request = json.loads(line or "{}")
                if not isinstance(request, dict):
                    raise ValueError("Each request must be a JSON object.")
                if args.output:
                    request = {**request, "stream": True}
                result = execute(owner, principal, args.operation, request, content=content)
                if args.output and result.status in {"completed", "partial"}:
                    from .interchange import open_artifact
                    output = Path(args.output)
                    parent = output.parent.resolve(strict=True)
                    if args.file_root and not parent.is_relative_to(Path(args.file_root).resolve(strict=True)):
                        raise ValueError("The requested output is outside --file-root.")
                    metadata, source = open_artifact(owner, result.data["artifact_id"], context=principal.context())
                    # Exclusive creation: never overwrite user work or follow an existing link.
                    with source, (parent / output.name).open("xb") as destination:
                        while chunk := source.read(1024 * 1024):
                            destination.write(chunk)
            except (ValueError, UnicodeError) as error:
                result = failure("invalid_request", str(error))
                framing_error = True
                stderr.write("Invalid JSON request.\n")
            _emit(result.public_dict(), stdout)
            code = max(code, 64 if framing_error else EXIT_CODES[result.status])
        return code
    except KeyboardInterrupt:
        _emit(OperationResult("cancelled").public_dict(), stdout)
        return 3
    except (ValueError, OSError, TypeError, ImportError) as error:
        stderr.write(f"Configuration/input error: {type(error).__name__}.\n")
        _emit(failure("invalid_configuration", "Check trusted configuration, input paths, and installed extras.")
              .public_dict(), stdout)
        return 64
    finally:
        if owner is not None and engine is None:
            from .interchange import cleanup_artifacts
            cleanup_artifacts(owner)


if __name__ == "__main__":
    raise SystemExit(main())
