import json
from radar import main as M


class Ok:
    @staticmethod
    def run(days_back): return 1


class Ko:
    @staticmethod
    def run(days_back): raise TimeoutError("timed out")


def test_alerte_seulement_apres_3_echecs(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "DATA", tmp_path)
    monkeypatch.setattr(M, "PAUSE", lambda s: None)
    monkeypatch.setattr(M, "SOURCES", (("A", Ok), ("B", Ko)))
    import radar.export as E
    monkeypatch.setattr(E, "build", lambda: {"count": 0})
    assert M.main(1) == 0 and M.main(1) == 0      # échecs 1 et 2 : pas d'alerte
    assert M.main(1) == 1                          # 3e d'affilée : alerte
    assert json.loads((tmp_path / "_etat.json").read_text())["sources"]["B"]["echecs_suite"] == 3
    assert [M.main(1) for _ in range(9)] == [0] * 8 + [1]   # 4e à 11e : silence, 12e : rappel quotidien
    monkeypatch.setattr(M, "SOURCES", (("B", Ok),))
    assert M.main(1) == 0
    assert json.loads((tmp_path / "_etat.json").read_text())["sources"]["B"]["echecs_suite"] == 0


def test_reessai_reussi(tmp_path, monkeypatch):
    n = {"c": 0}
    class Flaky:
        @staticmethod
        def run(days_back):
            n["c"] += 1
            if n["c"] == 1: raise TimeoutError("lent")
            return 2
    monkeypatch.setattr(M, "DATA", tmp_path)
    monkeypatch.setattr(M, "PAUSE", lambda s: None)
    monkeypatch.setattr(M, "SOURCES", (("F", Flaky),))
    import radar.export as E
    monkeypatch.setattr(E, "build", lambda: {"count": 0})
    assert M.main(1) == 0 and n["c"] == 2
