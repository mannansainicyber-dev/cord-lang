# Cord HTTP & External REST API Client

Cord features a native, non-blocking asynchronous HTTP client built directly into the runtime. You do not need to install `requests`, `aiohttp`, or `httpx`, or deal with session lifetimes and event-loop threading.

---

## 1. The `fetch()` Function

`fetch(url, [options])` performs an asynchronous HTTP GET request and returns a wrapped `Response` object.

```cord
command quote:
    res = fetch("https://dummyjson.com/quotes/random")
    if res.ok:
        reply "\"{res.quote}\" — **{res.author}**"
    else:
        reply "Could not load quote (Status {res.status})"
```

---

## 2. The `http` Module

For full REST workflows, Cord provides the `http` namespace:
- `http.get(url, [headers=...], [params=...])`
- `http.post(url, [json=...], [headers=...])`
- `http.delete(url, [headers=...])`

### Sending a POST Request with JSON Body

```cord
command notify_webhook(incident_msg: String):
    payload = {
        "text": incident_msg,
        "author": author.name,
        "timestamp": time.now()
    }
    
    res = http.post("https://my-webhook.internal/alerts", json=payload)
    if res.ok:
        reply "✅ Webhook alert delivered!"
    else:
        reply "❌ Failed to deliver webhook: HTTP {res.status}"
```

---

## 3. The `Response` Object

When `fetch()` or `http.*` completes, it returns a `Response` object with the following properties:

| Property | Type | Description |
| :--- | :--- | :--- |
| `res.status` | `Integer` | HTTP response status code (e.g. `200`, `404`, `500`). |
| `res.ok` | `Boolean` | `true` if `200 <= status < 300`, `false` otherwise. |
| `res.text` | `String` | Raw response body text. |
| `res.headers` | `Map` | HTTP response headers dictionary. |

### Intuitive Dot-Notation JSON Proxy

If the response returns `application/json`, Cord allows you to traverse JSON keys directly on the response object using natural dot notation or index subscripts:

```cord
command btc:
    res = fetch("https://api.coindesk.com/v1/bpi/currentprice.json")
    if res.ok:
        usd_price = res.bpi.USD.rate
        reply "💰 Current Bitcoin Price: **${usd_price} USD**"
```

Array indexes are accessed using standard bracket notation:

```cord
command latest_repo(username: String):
    res = fetch("https://api.github.com/users/{username}/repos")
    if res.ok and len(res) > 0:
        first_repo = res[0]
        reply "Latest repo: **{first_repo.name}** ({first_repo.stargazers_count} ⭐)"
```

---

## 4. Custom Headers & Query Parameters

You can pass authentication tokens, user agents, or custom headers using the `headers` option:

```cord
command weather(city: String):
    headers = {
        "Authorization": "Bearer " + env("WEATHER_API_KEY"),
        "User-Agent": "CordBot/1.0"
    }
    params = {
        "q": city,
        "units": "metric"
    }
    res = http.get("https://api.openweathermap.org/data/2.5/weather", headers=headers, params=params)
    if res.ok:
        temp = res.main.temp
        desc = res.weather[0].description
        reply "🌤️ Current temperature in **{city}**: **{temp}°C** ({desc})"
```

---

## 5. Non-Blocking Async Execution

Cord runs all HTTP requests asynchronously in the background. While waiting for an external server to respond, other Discord events, commands, and tasks continue executing without latency or gateway blocking.
