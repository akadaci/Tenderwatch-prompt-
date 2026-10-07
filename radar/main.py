"""Lance toutes les collectes. Une source en panne n'empêche pas les autres ; le code de sortie le signale."""
import sys, traceback
from radar import ted, nova

def main(days_back=7):
    errors = []
    for name, mod in (("TED", ted), ("Permis Bruxelles", nova)):
        try:
            mod.run(days_back=days_back)
        except Exception as e:
            errors.append(name)
            print(f"::error::{name} : {type(e).__name__}: {e}")
            traceback.print_exc()
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 7))
