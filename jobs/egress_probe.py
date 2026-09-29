"""Diagnostic job: record which outbound HTTPS hosts serverless job compute can reach."""

import json
import urllib.request

HOSTS = [
    "https://pypi.org/simple/onnxruntime/",
    "https://example.com/",
    "https://api.github.com/",
    "https://www.wikipedia.org/",
    "https://data.cityofnewyork.us/resource/erm2-nwe9.json?$limit=1",
]

if __name__ == "__main__":
    report = {}
    for url in HOSTS:
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                report[url] = f"HTTP {response.status}"
        except OSError as exc:  # URLError, HTTPError and timeouts are OSError subclasses
            report[url] = f"{type(exc).__name__}: {str(exc)[:160]}"
    print(json.dumps(report, indent=2))
