"""
Ombre Self-Hosted REST Server
==============================
Runs entirely on the customer's own infrastructure.
Exposes a REST API so any language can call Ombre.
Zero data leaves the customer's environment.

Usage:
    from ombre import Ombre
    ai = Ombre(openai_key="sk-...")
    ai.serve(host="0.0.0.0", port=8080)

Endpoints:
    POST /v1/run          - Single prompt
    POST /v1/chat         - Multi-turn chat
    POST /v1/batch        - Batch prompts
    POST /v1/embed        - Embeddings
    GET  /v1/stats        - Pipeline statistics
    GET  /v1/health       - Health check
    POST /v1/feedback     - Record user feedback
    GET  /v1/audit/export - Export audit logs
"""

from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from .utils.logger import get_logger

logger = get_logger(__name__)


class OmbreRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Ombre REST server."""

    ombre = None  # Injected by OmbreServer

    def log_message(self, format, *args):
        logger.debug(f"HTTP {args[0]} {args[1]}")

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        routes = {
            "/v1/run": self._handle_run,
            "/v1/chat": self._handle_chat,
            "/v1/batch": self._handle_batch,
            "/v1/embed": self._handle_embed,
            "/v1/feedback": self._handle_feedback,
        }
        handler = routes.get(path)
        if handler:
            body = self._read_body()
            if body is not None:
                handler(body)
        else:
            self._send_error(404, f"Route not found: {path}")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path == "/v1/health":
            self._handle_health()
        elif path == "/v1/stats":
            self._handle_stats()
        elif path == "/v1/audit/export":
            params = parse_qs(parsed.query)
            self._handle_audit_export(params)
        else:
            self._send_error(404, f"Route not found: {path}")

    def _handle_run(self, body: Dict[str, Any]) -> None:
        prompt = body.get("prompt", "")
        if not prompt:
            self._send_error(400, "prompt is required")
            return
        try:
            response = self.ombre.run(
                prompt=prompt,
                context=body.get("context"),
                system=body.get("system"),
                model=body.get("model", "auto"),
                agents=body.get("agents"),
                session_id=body.get("session_id"),
                user_id=body.get("user_id"),
                metadata=body.get("metadata", {}),
                temperature=float(body.get("temperature", 0.7)),
                max_tokens=int(body.get("max_tokens", 2048)),
            )
            self._send_json(response.to_dict())
        except Exception as e:
            self._send_error(500, str(e))

    def _handle_chat(self, body: Dict[str, Any]) -> None:
        messages = body.get("messages", [])
        if not messages:
            self._send_error(400, "messages is required")
            return
        try:
            response = self.ombre.chat(
                messages=messages,
                model=body.get("model", "auto"),
                session_id=body.get("session_id"),
                user_id=body.get("user_id"),
                system=body.get("system"),
                temperature=float(body.get("temperature", 0.7)),
                max_tokens=int(body.get("max_tokens", 2048)),
            )
            self._send_json(response.to_dict())
        except Exception as e:
            self._send_error(500, str(e))

    def _handle_batch(self, body: Dict[str, Any]) -> None:
        prompts = body.get("prompts", [])
        if not prompts:
            self._send_error(400, "prompts is required")
            return
        try:
            responses = self.ombre.batch(
                prompts=prompts,
                model=body.get("model", "auto"),
                concurrency=int(body.get("concurrency", 5)),
            )
            self._send_json({
                "responses": [r.to_dict() for r in responses],
                "count": len(responses),
            })
        except Exception as e:
            self._send_error(500, str(e))

    def _handle_embed(self, body: Dict[str, Any]) -> None:
        text = body.get("text", "")
        if not text:
            self._send_error(400, "text is required")
            return
        try:
            result = self.ombre.embed(text=text, model=body.get("model", "auto"))
            self._send_json(result)
        except Exception as e:
            self._send_error(500, str(e))

    def _handle_feedback(self, body: Dict[str, Any]) -> None:
        request_id = body.get("request_id", "")
        rating = body.get("rating", 0)
        if not request_id:
            self._send_error(400, "request_id is required")
            return
        if not (1 <= int(rating) <= 5):
            self._send_error(400, "rating must be between 1 and 5")
            return
        try:
            self.ombre.feedback.record_user_feedback(
                request_id=request_id,
                rating=int(rating),
                comment=body.get("comment"),
                outcome=body.get("outcome"),
            )
            self._send_json({"status": "recorded", "request_id": request_id})
        except Exception as e:
            self._send_error(500, str(e))

    def _handle_health(self) -> None:
        self._send_json({
            "status": "ok",
            "version": self.ombre.VERSION,
            "session": self.ombre.session_id,
            "providers": self.ombre.config.available_providers,
            "timestamp": time.time(),
            "data_policy": "All data stays on your infrastructure. Nothing is transmitted externally.",
        })

    def _handle_stats(self) -> None:
        self._send_json(self.ombre.stats())

    def _handle_audit_export(self, params: Dict[str, Any]) -> None:
        import tempfile
        fmt = params.get("format", ["json"])[0]
        with tempfile.NamedTemporaryFile(mode="w", suffix=f".{fmt}", delete=False) as f:
            path = f.name
        try:
            exported = self.ombre.export_audit(output_path=path, format=fmt)
            with open(exported, "r") as f:
                content = f.read()
            content_types = {"json": "application/json", "csv": "text/csv", "jsonl": "application/x-ndjson"}
            self._send_response(200, content.encode(), content_types.get(fmt, "text/plain"))
        except Exception as e:
            self._send_error(500, str(e))

    def _read_body(self) -> Optional[Dict[str, Any]]:
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                return {}
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))
        except Exception as e:
            self._send_error(400, f"Invalid JSON: {e}")
            return None

    def _send_json(self, data: Any) -> None:
        body = json.dumps(data, default=str).encode("utf-8")
        self._send_response(200, body, "application/json")

    def _send_error(self, status: int, message: str) -> None:
        body = json.dumps({"error": message, "status": status}).encode("utf-8")
        self._send_response(status, body, "application/json")

    def _send_response(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Powered-By", "Ombre")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


class OmbreServer:
    """
    Self-hosted Ombre REST server.
    Runs entirely on the customer's own infrastructure.
    """

    def __init__(self, ombre_instance: Any):
        self.ombre = ombre_instance
        OmbreRequestHandler.ombre = ombre_instance

    def run(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        server = HTTPServer((host, port), OmbreRequestHandler)
        logger.info(f"Ombre self-hosted server on http://{host}:{port}")
        logger.info("  POST /v1/run    POST /v1/chat    POST /v1/batch")
        logger.info("  POST /v1/embed  GET  /v1/health  GET  /v1/stats")
        logger.info("  POST /v1/feedback    GET /v1/audit/export")
        logger.info("Your data never leaves this machine.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Ombre server stopped")
            server.server_close()
