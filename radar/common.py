"""Outils communs : écriture des fiches au format Radar Chantiers."""
import json, re
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
STAGES = {1: "Projet repéré", 2: "Bureau d'études connu", 3: "CDC en rédaction", 4: "Publié",
          5: "Attribué", 6: "Sous-traitants connus", 7: "Chantier en cours", 8: "Terminé"}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def clean(s, n=300):
    return " ".join(str(s).split())[:n] if s not in (None, "") else ""


def save(name, records, meta):
    """Fusionne avec le fichier existant (clé = id) pour garder l'historique ; écrit data/<name>.json."""
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / f"{name}.json"
    old = {}
    if path.exists():
        try:
            old = {r["id"]: r for r in json.loads(path.read_text())["records"]}
        except (ValueError, KeyError):
            old = {}
    new_ids = [r["id"] for r in records if r["id"] not in old]
    for r in records:
        r.setdefault("first_seen", old.get(r["id"], {}).get("first_seen") or now_iso())
        old[r["id"]] = {**old.get(r["id"], {}), **r}
    out = sorted(old.values(), key=lambda r: r.get("date_publication") or "", reverse=True)
    path.write_text(json.dumps({"updated": now_iso(), **meta, "count": len(out), "new_ids": new_ids,
                                "records": out}, ensure_ascii=False, indent=1))
    return len(new_ids), len(out)
