import ast
import datetime as dt
import operator
import re
from typing import Any
from urllib.parse import quote

import requests


SEARCH_URL = "https://api.duckduckgo.com/"
NEWS_RSS_URL = "https://news.google.com/rss/search"
FX_URL = "https://economia.awesomeapi.com.br/json/last"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def safe_calculate(expression: str) -> float:
    expression = expression.strip().replace(",", ".")
    expression = expression.replace("^", "**")
    if len(expression) > 120:
        raise ValueError("Expressão muito longa.")
    tree = ast.parse(expression, mode="eval")

    def walk(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            left, right = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 20:
                raise ValueError("Potência muito grande.")
            return _BIN_OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return _UNARY_OPS[type(node.op)](walk(node.operand))
        raise ValueError("Expressão não permitida.")

    value = walk(tree.body)
    if abs(value) > 1e100:
        raise ValueError("Resultado muito grande.")
    return value


def web_search(query: str, limit: int = 5) -> dict[str, Any]:
    query = query.strip()[:300]
    if not query:
        return {"summary": "", "sources": []}
    response = requests.get(
        SEARCH_URL,
        params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
        headers={"User-Agent": "Cosmo/1.0"},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    sources: list[dict[str, str]] = []

    abstract = data.get("AbstractText") or ""
    abstract_url = data.get("AbstractURL") or ""
    heading = data.get("Heading") or ""
    if abstract:
        sources.append({"title": heading or query, "url": abstract_url, "snippet": abstract})

    for item in data.get("Results") or []:
        if len(sources) >= limit:
            break
        if isinstance(item, dict) and item.get("FirstURL"):
            sources.append({
                "title": item.get("Result", "Resultado").replace("<b>", "").replace("</b>", ""),
                "url": item["FirstURL"],
                "snippet": item.get("Text", ""),
            })

    def add_topics(items: list[Any]) -> None:
        for item in items:
            if len(sources) >= limit:
                return
            if isinstance(item, dict) and item.get("FirstURL"):
                sources.append({
                    "title": item.get("Text", "Resultado")[:90],
                    "url": item["FirstURL"],
                    "snippet": item.get("Text", ""),
                })
            elif isinstance(item, dict) and isinstance(item.get("Topics"), list):
                add_topics(item["Topics"])

    add_topics(data.get("RelatedTopics") or [])
    summary = abstract or (sources[0]["snippet"] if sources else "")
    return {"summary": summary[:4000], "sources": sources[:limit]}



def exchange_rate(pair: str = "USD-BRL") -> dict[str, Any]:
    """Busca a última cotação do par cambial usando a AwesomeAPI."""
    import os as _os
    api_key = _os.getenv("AWESOMEAPI_KEY", "").strip()
    headers = {"User-Agent": "Cosmo/1.0"}
    if api_key:
        headers["x-api-key"] = api_key
    response = requests.get(
        f"{FX_URL}/{pair}",
        headers=headers,
        timeout=8,
    )
    response.raise_for_status()
    data = response.json()
    quote = data.get(pair.replace("-", "")) or {}
    if not quote:
        raise ValueError(f"Cotação não encontrada para {pair}.")
    return quote


def current_news_search(query: str, limit: int = 5) -> dict[str, Any]:
    """Fallback de pesquisa atual usando Google News RSS, sem chave de API."""
    response = requests.get(
        NEWS_RSS_URL,
        params={"q": query[:180], "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"},
        headers={"User-Agent": "Cosmo/1.0"},
        timeout=10,
    )
    response.raise_for_status()
    import xml.etree.ElementTree as ET
    root = ET.fromstring(response.text)
    items = []
    for item in root.findall(".//item")[:limit]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = re.sub(r"<[^>]+>", " ", item.findtext("description") or "")
        description = re.sub(r"\s+", " ", description).strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        if title or link:
            items.append({"title": title, "url": link, "snippet": description[:500], "published": pub_date})
    summary = " ".join(x["snippet"] for x in items if x["snippet"])[:4000]
    return {"summary": summary, "sources": items}

def weather(city: str) -> dict[str, Any]:
    city = city.strip()[:100]
    response = requests.get(
        GEOCODE_URL,
        params={"name": city, "count": 1, "language": "pt", "format": "json"},
        headers={"User-Agent": "Cosmo/1.0"},
        timeout=8,
    )
    response.raise_for_status()
    result = (response.json().get("results") or [])
    if not result:
        return {"error": f"Não encontrei a cidade {city}."}
    place = result[0]
    forecast = requests.get(
        FORECAST_URL,
        params={
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
            "timezone": "auto",
        },
        headers={"User-Agent": "Cosmo/1.0"},
        timeout=8,
    )
    forecast.raise_for_status()
    current = forecast.json().get("current", {})
    return {
        "city": place.get("name", city),
        "country": place.get("country", ""),
        "temperature": current.get("temperature_2m"),
        "humidity": current.get("relative_humidity_2m"),
        "wind": current.get("wind_speed_10m"),
        "weather_code": current.get("weather_code"),
        "time": current.get("time"),
    }


def detect_weather_city(text: str) -> str | None:
    match = re.search(r"(?:tempo|clima|previs[aã]o).*?\bem\s+([A-Za-zÀ-ÿ .'-]{2,80})", text, re.I)
    if match:
        return match.group(1).strip(" ?!.,")
    return None


def detect_calculation(text: str) -> str | None:
    cleaned = text.strip()
    if re.fullmatch(r"[0-9+\-*/().,% ^]+", cleaned) and any(c.isdigit() for c in cleaned):
        return cleaned
    match = re.search(r"(?:calcule|calcular|quanto [eé]|resultado de)\s+(.+)$", cleaned, re.I)
    if match and re.fullmatch(r"[0-9+\-*/().,% ^]+", match.group(1).strip()):
        return match.group(1).strip()
    return None


def build_tool_context(text: str, force_search: bool = False) -> tuple[str, list[dict[str, Any]]]:
    lower = text.lower().strip()
    context: list[str] = []
    used: list[dict[str, Any]] = []

    expression = detect_calculation(text)
    if expression:
        try:
            value = safe_calculate(expression)
            result = f"{value:g}"
            context.append(f"CALCULADORA: expressão {expression!r} = {result}.")
            used.append({"tool": "calculator", "label": "Calculadora"})
        except Exception:
            pass

    if any(key in lower for key in ("que horas", "horas agora", "hora atual")):
        now = dt.datetime.now().astimezone()
        context.append(
            f"HORA ATUAL DO SERVIDOR: {now.strftime('%d/%m/%Y %H:%M:%S %z')}."
        )
        used.append({"tool": "time", "label": "Hora atual"})

    city = detect_weather_city(text)
    if city:
        try:
            data = weather(city)
            if "error" not in data:
                context.append(
                    "CLIMA ATUAL: "
                    f"{data['city']} ({data['country']}), "
                    f"{data.get('temperature')}°C, umidade {data.get('humidity')}%, "
                    f"vento {data.get('wind')} km/h, código meteorológico {data.get('weather_code')}."
                )
                used.append({"tool": "weather", "label": f"Clima — {data['city']}"})
        except requests.RequestException:
            pass

    wants_fx = any(
        phrase in lower
        for phrase in (
            "cotação do dólar",
            "cotação atual do dólar",
            "dólar hoje",
            "dólar agora",
            "usd para brl",
            "usd/brl",
            "quanto está o dólar",
            "quanto vale o dólar",
            "preço do dólar",
        )
    )
    fx_found = False
    if wants_fx:
        try:
            quote = exchange_rate("USD-BRL")
            fx_found = True
            context.append(
                "COTAÇÃO ONLINE DO DÓLAR (USD/BRL): "
                f"compra R$ {quote.get('bid')}, venda R$ {quote.get('ask')}, "
                f"máxima R$ {quote.get('high')}, mínima R$ {quote.get('low')}, "
                f"variação {quote.get('pctChange')}%, atualização "
                f"{quote.get('create_date') or quote.get('timestamp')}. "
                "Fonte: AwesomeAPI."
            )
            used.append({
                "tool": "currency",
                "label": "Dólar USD/BRL",
                "source": "AwesomeAPI",
                "bid": quote.get("bid"),
                "ask": quote.get("ask"),
                "high": quote.get("high"),
                "low": quote.get("low"),
                "pctChange": quote.get("pctChange"),
                "updated": quote.get("create_date") or quote.get("timestamp")
            })
        except (requests.RequestException, ValueError):
            pass

    wants_search = force_search or any(
        phrase in lower
        for phrase in (
            "pesquise ",
            "pesquisa ",
            "procure na internet",
            "procure na web",
            "busque na internet",
            "busque na web",
            "pesquise na internet",
            "pesquise na web",
            "cotação atual",
            "cotação do dólar",
            "dólar hoje",
            "último jogo",
            "último resultado",
            "resultado de hoje",
            "jogo de hoje",
            "notícias de hoje",
            "notícia de hoje",
            "hoje",
            "agora",
            "atual",
            "atualmente",
        )
    )
    if wants_search and not fx_found:
        query = re.sub(
            r"^(pesquise|pesquisa|procure na internet|procure na web|busque na internet|busque na web|pesquise na internet|pesquise na web)[: ]*",
            "",
            text.strip(),
            flags=re.I,
        ).strip()
        try:
            data = web_search(query)
            if not data["summary"] and not data["sources"]:
                data = current_news_search(query)
            if data["summary"]:
                context.append("PESQUISA ATUAL: " + data["summary"])
            if data["sources"]:
                source_text = "; ".join(
                    f"{s['title']} — {s['url']}" for s in data["sources"] if s.get("url")
                )
                context.append("FONTES DA PESQUISA: " + source_text)
            if data["summary"] or data["sources"]:
                used.append({"tool": "web", "label": "Pesquisa atual na web", "sources": data["sources"]})
        except requests.RequestException:
            pass

    if not context:
        return "", used
    return (
        "Ferramentas disponíveis para esta resposta. Use esses dados como contexto factual; "
        "não invente dados que não estejam aqui.\n" + "\n".join(context)
    ), used
