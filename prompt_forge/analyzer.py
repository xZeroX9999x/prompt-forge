"""Self-analysis: stats and feedback loop for improving compile quality over time."""
from . import db


class Analyzer:
    def print_stats(self):
        s = db.get_stats()
        print("\n📊 Prompt Forge — statistics\n" + "─" * 40)
        print(f"  Total compilations : {s['total_compilations']}")
        print(f"  Techniques in KB   : {s['total_techniques']}")
        print(f"  Successful fetches : {s['successful_fetches']}")
        if s["avg_rating"]:
            print(f"  Average rating     : {s['avg_rating']} / 5")
        else:
            print("  Average rating     : (no ratings yet — run 'forge rate')")

        if s["by_domain"]:
            print("\n  By domain:")
            for row in s["by_domain"]:
                d = row["domain"] or "(none)"
                print(f"    {d:<12} {row['n']}")

        if s["by_level"]:
            print("\n  By complexity:")
            for row in s["by_level"]:
                print(f"    L{row['level']:<10} {row['n']}")

        if s["top_techniques"]:
            print("\n  Top-weighted techniques:")
            for row in s["top_techniques"][:5]:
                print(f"    {row['name']:<40} {row['weight']:.2f}")

        print()

    def rate_last(self, score: int, note: str = "") -> bool:
        return db.rate_last_compilation(score, note)
