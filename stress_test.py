import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any

import requests
from flask import Flask, jsonify, request
from urllib.parse import urlparse

app = Flask(__name__)

def _build_headers(
    base_headers: Optional[Dict[str, str]],
    token: Optional[str],
    auth_scheme: Optional[str],
) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if base_headers:
        headers.update(base_headers)

    if token and auth_scheme:
        scheme = auth_scheme.strip().lower()
        if scheme == "bearer":
            headers["Authorization"] = f"Bearer {token}"
        elif scheme == "basic":
            headers["Authorization"] = f"Basic {token}"

    return headers


def _method_func(session: requests.Session, method_upper: str):
    mapping = {
        "GET": session.get,
        "POST": session.post,
        "PUT": session.put,
        "PATCH": session.patch,
        "DELETE": session.delete,
    }
    if method_upper not in mapping:
        raise ValueError(f"Unsupported method: {method_upper}")
    return mapping[method_upper]


def _parse_response(resp: requests.Response) -> Any:
    ct = resp.headers.get("Content-Type", "")
    if "application/json" in ct:
        try:
            return resp.json()
        except Exception:
            return resp.text
    return resp.text


def _do_request(
    i: int,
    session: requests.Session,
    url: str,
    method_upper: str,
    headers: Optional[Dict[str, str]],
    body: Optional[Any],
    tokens: Optional[List[str]],
    auth_scheme: Optional[str],
    timeout: float,
) -> Dict[str, Any]:
    token = random.choice(tokens) if tokens else None
    req_headers = _build_headers(headers, token, auth_scheme)
    start = time.time()
    try:
        func = _method_func(session, method_upper)
        kwargs: Dict[str, Any] = {"headers": req_headers, "timeout": timeout}
        if method_upper in ("POST", "PUT", "PATCH"):
            kwargs["json"] = body
        resp = func(url, **kwargs)

        duration = time.time() - start
        payload = _parse_response(resp)
        return {
            "index": i,
            "status_code": resp.status_code,
            "ok": resp.ok,
            "time_ms": round(duration * 1000, 2),
            "response": payload,
        }
    except Exception as e:
        duration = time.time() - start
        return {
            "index": i,
            "error": str(e),
            "ok": False,
            "time_ms": round(duration * 1000, 2),
        }


def run_stress_test(
    url: str,
    total_requests: int = 100,
    max_workers: int = 10,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Any] = None,
    tokens: Optional[List[str]] = None,
    auth_scheme: Optional[str] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Run a stress test against the given URL and return summary + results."""

    session = requests.Session()
    method_upper = method.upper()

    results: List[Dict[str, Any]] = []
    latencies: List[float] = []
    success = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                _do_request,
                i,
                session,
                url,
                method_upper,
                headers,
                body,
                tokens,
                auth_scheme,
                timeout,
            )
            for i in range(total_requests)
        ]
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            latencies.append(res.get("time_ms", 0))
            if res.get("ok"):
                success += 1

    failed = total_requests - success
    latencies_sorted = sorted(latencies) if latencies else []

    def pct(p: float) -> Optional[float]:
        if not latencies_sorted:
            return None
        k = int(round((p / 100.0) * (len(latencies_sorted) - 1)))
        return latencies_sorted[k]

    summary = {
        "total_requests": total_requests,
        "success": success,
        "failed": failed,
        "avg_time_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "p50_time_ms": pct(50),
        "p95_time_ms": pct(95),
        "p99_time_ms": pct(99),
    }

    return {"summary": summary, "results": results}

def _validate_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


@app.route("/health", methods=["GET"])
def health() -> Any:
    return jsonify({"status": "ok"})


@app.route("/stress-test", methods=["POST"])
def stress_test_endpoint() -> Any:
    data = request.get_json(silent=True) or {}

    url: Optional[str] = data.get("url")
    if not url or not _validate_url(url):
        return (
            jsonify({"error": "Invalid or missing 'url'. Must be http/https."}),
            400,
        )

    method: str = (data.get("method") or "GET").upper()
    total_requests: int = int(data.get("total_requests") or 100)
    max_workers: int = int(data.get("max_workers") or 10)
    headers: Optional[Dict[str, str]] = data.get("headers")
    body: Optional[Any] = data.get("body")
    tokens: Optional[List[str]] = data.get("tokens")
    auth_scheme: Optional[str] = data.get("auth_scheme")
    timeout: float = float(data.get("timeout") or 30.0)
    include_results: bool = bool(data.get("include_results") if "include_results" in data else False)

    if total_requests <= 0 or max_workers <= 0:
        return (
            jsonify({"error": "'total_requests' and 'max_workers' must be > 0"}),
            400,
        )

    try:
        output = run_stress_test(
            url=url,
            total_requests=total_requests,
            max_workers=max_workers,
            method=method,
            headers=headers,
            body=body,
            tokens=tokens,
            auth_scheme=auth_scheme,
            timeout=timeout,
        )
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if not include_results:
        return jsonify({"summary": output["summary"]})

    return jsonify(output)
