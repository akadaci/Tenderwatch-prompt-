"""Lance toutes les collectes. Une source en panne n'empêche pas les autres.
L'état de chaque source (succès, nouveaux avis, erreur) est écrit dans data/_etat.json."""
import json, sys, traceback
from radar import ted, nova, bda
from radar.common import DATA, now_iso

SOURCES = (("TED", ted), ("Bulletin des Adjudications", bda), ("Permis Bruxelles", nova))


def main(days_back=7):
    etat, errors = {"updated": now_iso(), "days_back": days_back, "sources": {}}, []
    for name, mod in SOURCES:
        try:
            new = mod.run(days_back=days_back)
            etat["sources"][name] = {"ok": True, "new": new}
        except Exception as e:
            errors.append(name)
            etat["sources"][name] = {"ok": False, "error": f"{type(e).__name__}: {e}"[:1000],
                                     "trace": traceback.format_exc()[-2500:]}
            print(f"::error::{name} : {type(e).__name__}: {e}")
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "_etat.json").write_text(json.dumps(etat, ensure_ascii=False, indent=1))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 7))
