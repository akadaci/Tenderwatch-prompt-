"""Lance toutes les collectes. Une source en panne n'empêche pas les autres.
L'état de chaque source (succès, nouveaux avis, erreur, échecs d'affilée) est écrit dans data/_etat.json.
Une source qui échoue est retentée une fois ; l'alerte (code 1 → e-mail GitHub) part au 3e échec consécutif,
puis une fois par jour si la panne dure (pas un e-mail toutes les 2 h)."""
import json, sys, time, traceback
from radar import ted, nova, bda
from radar.common import DATA, now_iso

SOURCES = (("TED", ted), ("Bulletin des Adjudications", bda), ("Permis Bruxelles", nova))
ALERTE = 3
RAPPEL = 12      # si la panne dure : un rappel par jour (12 collectes), pas un e-mail toutes les 2 h
PAUSE = time.sleep


def _precedent():
    try:
        return json.loads((DATA / "_etat.json").read_text()).get("sources", {})
    except Exception:
        return {}


def main(days_back=7):
    avant = _precedent()
    etat, alertes = {"updated": now_iso(), "days_back": days_back, "sources": {}}, []
    for name, mod in SOURCES:
        for essai in (1, 2):
            try:
                new = mod.run(days_back=days_back)
                etat["sources"][name] = {"ok": True, "new": new, "echecs_suite": 0}
                break
            except Exception as e:
                if essai == 1:
                    print(f"::warning::{name} : {type(e).__name__}: {e} — nouvel essai dans 30 s")
                    PAUSE(30)
                    continue
                n = int(avant.get(name, {}).get("echecs_suite", 0)) + 1
                etat["sources"][name] = {"ok": False, "echecs_suite": n, "error": f"{type(e).__name__}: {e}"[:1000],
                                         "trace": traceback.format_exc()[-2500:]}
                if n == ALERTE or (n > ALERTE and n % RAPPEL == 0):
                    alertes.append(name)
                    print(f"::error::{name} en panne depuis {n} collectes : {type(e).__name__}: {e}")
                else:
                    print(f"::warning::{name} : échec n°{n} ({type(e).__name__}: {e}) — e-mail seulement au 3e échec puis une fois par jour")
    try:
        from radar import export
        etat["radar_public"] = export.build()["count"]
    except Exception as e:
        alertes.append("export")
        etat["radar_public_error"] = f"{type(e).__name__}: {e}"
        print(f"::error::export : {type(e).__name__}: {e}")
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "_etat.json").write_text(json.dumps(etat, ensure_ascii=False, indent=1))
    return 1 if alertes else 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 7))
