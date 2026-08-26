"""Cloud Run HTTP launch surface for prem3-mta-worker jobs.

Cloud Tasks OIDC hits POST /internal/v1/mta-dispatches/{id}/launch.
Cloud Run IAM rejects unauthenticated callers; this process then starts the Job.
"""

from __future__ import annotations

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.modeling.mta.jobs import CloudRunMTAJobLauncher, JobLaunchError

LAUNCH_PATH = re.compile(r"^/internal/v1/mta-dispatches/([^/]+)/launch/?$")
HEALTH_PATH = "/health"


class MTALaunchHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} {fmt % args}")

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] == HEALTH_PATH:
            self._json(200, {"ok": True})
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        match = LAUNCH_PATH.match(path)
        if match is None:
            self._json(404, {"error": "not_found"})
            return
        if not (self.headers.get("Authorization") or self.headers.get("authorization")):
            self._json(401, {"error": "service_identity_required"})
            return
        dispatch_id = match.group(1)
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get(
            "M3_GCP_PROJECT"
        ) or "modelready-m3"
        region = os.environ.get("GOOGLE_CLOUD_REGION") or "us-central1"
        try:
            execution = CloudRunMTAJobLauncher(
                project_id=project_id, location=region
            ).launch(dispatch_id)
        except JobLaunchError as exc:
            self._json(503, {"error": "job_launch_failed", "detail": str(exc)})
            return
        self._json(200, {"dispatch_id": dispatch_id, "status": "LAUNCHED", "execution": execution})

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    port = int(os.environ.get("PORT") or "8080")
    server = ThreadingHTTPServer(("0.0.0.0", port), MTALaunchHandler)
    print(f"mta-launch listening on {port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
