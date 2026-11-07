"""Relevé des cotes pour le simulateur « Toi contre Claude ».

Lancé par GitHub Actions (voir .github/workflows/releve-cotes.yml).
La clé The Odds API vient du secret ODDS_API_KEY : elle n'apparaît jamais dans ce dépôt.

Écrit :
  data/latest.json                      dernier relevé complet
  data/snapshots/AAAA-MM-JJ/HHMM.json   historique (sert à la cote de clôture / CLV)
  data/status.json                      état du dernier passage (crédits restants, erreurs)
"""
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.the-odds-api.com/v4"
# Jusqu'à 10 bookmakers comptent comme une seule région : 1 crédit par compétition et par relevé.
BOOKMAKERS = ["betclic_fr", "pinnacle", "unibet_fr", "winamax_fr"]
# Compétitions suivies (préfixes des clés de sport). Ajouter "tennis_wta_" pour le tennis féminin.
PREFIXES = ("tennis_atp_", "mma_mixed_martial_arts")
MIN_CREDITS = 15          # en dessous, on arrête pour ne pas épuiser le quota du mois
KEEP_DAYS = 60            # durée de conservation des relevés détaillés
ROOT = pathlib.Path(__file__).resolve().parent.parent / "data"


def get(path, params, key):
    url = f"{BASE}{path}?{urllib.parse.urlencode({**params, 'apiKey': key})}"
    req = urllib.request.Request(url, headers={"User-Agent": "releve-cotes-simulateur"})
    with urllib.request.urlopen(req, timeout=30) as r:
        headers = {k.lower(): v for k, v in r.headers.items()}
        return json.load(r), headers


def fair(prices):
    """Probabilités sans marge à partir d'un dict {nom: cote}."""
    inv = {n: 1 / p for n, p in prices.items() if p and p > 1}
    s = sum(inv.values())
    return {n: round(v / s, 4) for n, v in inv.items()} if s else {}


def simplify(event):
    books = {}
    for b in event.get("bookmakers", []):
        for m in b.get("markets", []):
            if m.get("key") != "h2h":
                continue
            prices = {o["name"]: o["price"] for o in m.get("outcomes", []) if o.get("name") != "Draw"}
            if len(prices) == 2:
                books[b["key"]] = {"prices": prices, "last_update": m.get("last_update") or b.get("last_update")}
    out = {
        "id": event["id"],
        "sport_key": event["sport_key"],
        "sport_title": event.get("sport_title"),
        "commence_time": event["commence_time"],
        "players": [event.get("home_team"), event.get("away_team")],
        "books": books,
    }
    if "pinnacle" in books:
        out["pinnacle_fair"] = fair(books["pinnacle"]["prices"])
    others = [v["prices"] for v in books.values()]
    if others:  # consensus : moyenne des probabilités sans marge de tous les bookmakers disponibles
        names = out["players"]
        probs = [fair(p) for p in others]
        out["consensus_fair"] = {n: round(sum(p.get(n, 0) for p in probs) / len(probs), 4) for n in names if n}
    return out


def collect(key, fetch=None):
    fetch = fetch or get
    sports, _ = fetch("/sports", {}, key)  # gratuit
    keys = sorted(s["key"] for s in sports
                  if s.get("active") and s["key"].startswith(PREFIXES) and not s.get("has_outrights"))
    events, remaining, used, errors = [], None, None, []
    for k in keys:
        if remaining is not None and int(float(remaining)) < MIN_CREDITS:
            errors.append(f"{k}: arrêté, plus que {remaining} crédits")
            continue
        try:
            data, h = fetch(f"/sports/{k}/odds", {"bookmakers": ",".join(BOOKMAKERS), "markets": "h2h",
                                                  "oddsFormat": "decimal", "dateFormat": "iso"}, key)
            remaining, used = h.get("x-requests-remaining", remaining), h.get("x-requests-used", used)
            events += [simplify(e) for e in data]
        except urllib.error.HTTPError as e:
            errors.append(f"{k}: HTTP {e.code}")
        except urllib.error.URLError as e:
            errors.append(f"{k}: réseau ({e.reason})")
    return keys, events, remaining, used, errors


def main():
    key = os.environ.get("ODDS_API_KEY", "").strip()
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    ROOT.mkdir(parents=True, exist_ok=True)
    status = {"run_at": now.isoformat().replace("+00:00", "Z")}
    if not key:
        status["error"] = "Secret ODDS_API_KEY absent"
        (ROOT / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=1))
        print(status["error"]); sys.exit(1)
    try:
        keys, events, remaining, used, errors = collect(key)
    except (urllib.error.HTTPError, urllib.error.URLError) as e:  # clé refusée, quota épuisé, réseau…
        status["error"] = f"Liste des sports inaccessible : {getattr(e, 'code', None) or getattr(e, 'reason', e)}"
        (ROOT / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=1))
        print(status["error"]); sys.exit(1)
    snap = {"fetched_at": status["run_at"], "sports": keys, "bookmakers": BOOKMAKERS, "events": events}
    (ROOT / "latest.json").write_text(json.dumps(snap, ensure_ascii=False, indent=1))
    day = ROOT / "snapshots" / now.strftime("%Y-%m-%d")
    day.mkdir(parents=True, exist_ok=True)
    (day / f"{now.strftime('%H%M')}.json").write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":")))
    cutoff = (now - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    for old in (ROOT / "snapshots").iterdir():
        if old.is_dir() and old.name < cutoff:
            for f in old.iterdir():
                f.unlink()
            old.rmdir()
    status.update({"sports": keys, "events": len(events), "credits_remaining": remaining,
                   "credits_used": used, "errors": errors})
    (ROOT / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=1))
    print(json.dumps(status, ensure_ascii=False))


if __name__ == "__main__":
    main()
