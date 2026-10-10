import json
import urllib.parse
import urllib.request
from .providers import validate_url, opener


def web_search(settings, query, timeout=15):
    if not settings.get("enabled"):
        raise ValueError("Search retrieval is disabled. Configure your SearXNG endpoint or use the browser Search button.")
    if len(query) > 500:
        raise ValueError("Search query too long")
    base = validate_url(settings["url"], "local", settings.get("allow_insecure_lan", False))
    url = base + "/search?" + urllib.parse.urlencode({"q": query, "format": "json"})
    with opener().open(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=timeout) as response:
        body = response.read(524289)
    if len(body) > 524288:
        raise ValueError("Search response too large")
    data = json.loads(body)
    results = []
    for result in data.get("results", [])[:5]:
        parsed = urllib.parse.urlsplit(result.get("url", ""))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            continue
        results.append({"title": str(result.get("title", ""))[:200], "url": result["url"],
                        "snippet": str(result.get("content", ""))[:600]})
    return results
