# --------------------------------------------------
# metrics.py
# --------------------------------------------------
# This module provides an in-process Prometheus-style
# metrics collector with thread-safe counters.
#
# It tracks:
#   ✔ Total HTTP requests (path + status)
#   ✔ Webhook outcomes (created / duplicate / invalid_signature / validation_error)
#   ✔ Simple latency buckets (<=100ms, <=500ms, +Inf)
#
# Exposed through /metrics using plain text exposition format.
# --------------------------------------------------

from collections import defaultdict
import threading


class Metrics:
    """
    Thread-safe metric collector designed for lightweight FastAPI services.
    All counters and histograms are stored in memory and reset on restart.
    """

    def __init__(self):
        # Ensure concurrent safety when updating counters
        self.lock = threading.Lock()

        # Count HTTP requests by (path, status)
        self.http_requests = defaultdict(int)

        # Count webhook message ingestion results
        self.webhook_requests = defaultdict(int)

        # Latency buckets: "100", "500", "+Inf"
        self.latency_buckets = defaultdict(int)

    # --------------------------------------------------
    # Increment HTTP request counter
    # --------------------------------------------------

    def inc_http(self, path: str, status: int):
        """
        Count an HTTP call labeled by (path, status).
        """
        with self.lock:
            self.http_requests[(path, str(status))] += 1

    # --------------------------------------------------
    # Increment webhook ingestion counter
    # --------------------------------------------------

    def inc_webhook(self, result: str):
        """
        Count webhook ingestion outcomes:
          - created
          - duplicate
          - invalid_signature
          - validation_error
        """
        with self.lock:
            self.webhook_requests[result] += 1

    # --------------------------------------------------
    # Observe latency in milliseconds
    # --------------------------------------------------

    def observe_latency(self, ms: float):
        """
        Record request latency into discrete buckets:
          <= 100 ms
          <= 500 ms
          > 500 ms
        """
        with self.lock:
            if ms <= 100:
                self.latency_buckets["100"] += 1
            elif ms <= 500:
                self.latency_buckets["500"] += 1
            else:
                self.latency_buckets["+Inf"] += 1

    # --------------------------------------------------
    # Render Prometheus exposition format
    # --------------------------------------------------

    def render_prometheus(self) -> str:
        """
        Produces text output in Prometheus-readable format.

        Examples:

            http_requests_total{path="/webhook",status="200"} 15
            webhook_requests_total{result="duplicate"} 3
            request_latency_ms_bucket{le="100"} 20
            request_latency_ms_bucket{le="500"} 25
            request_latency_ms_bucket{le="+Inf"} 25
            request_latency_ms_count 25
        """
        lines = []

        # HTTP request counters
        for (path, status), value in self.http_requests.items():
            lines.append(
                f'http_requests_total{{path="{path}",status="{status}"}} {value}'
            )

        # Webhook counters
        for result, value in self.webhook_requests.items():
            lines.append(
                f'webhook_requests_total{{result="{result}"}} {value}'
            )

        # Latency buckets
        count_100 = self.latency_buckets.get("100", 0)
        count_500 = self.latency_buckets.get("500", 0)
        count_inf = self.latency_buckets.get("+Inf", 0)
        total = count_100 + count_500 + count_inf

        lines.append(f'request_latency_ms_bucket{{le="100"}} {count_100}')
        lines.append(f'request_latency_ms_bucket{{le="500"}} {count_100 + count_500}')
        lines.append(f'request_latency_ms_bucket{{le="+Inf"}} {total}')
        lines.append(f'request_latency_ms_count {total}')

        # Final newline required by Prometheus
        return "\n".join(lines) + "\n"


# Global shared instance
metrics = Metrics()
