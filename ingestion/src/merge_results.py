"""
merge_results.py - join the slice files produced with --part / --range into ONE file.

    python3 merge_results.py                 # reads results/extracted_*.jsonl next to this script
    python3 merge_results.py --input ../data # also lists the articles that are still missing

Writes results/all_extracted_news.jsonl and results/all_extracted_news.json (duplicates by id are dropped, newest wins).
(They live inside the results folder so that they survive when this runs in Docker with results/ mounted.)
"""
import argparse
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

BASE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="the same --input you gave extract_crime.py (to report missing articles)")
    ap.add_argument("--results", default=str(BASE / "results"))
    args = ap.parse_args()

    files = sorted(Path(args.results).glob("extracted_*.jsonl"))
    if not files:
        raise SystemExit(f"No extracted_*.jsonl found in {args.results}")
    recs, dup, versions = {}, 0, {}
    for f in files:
        n = 0
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            n += 1
            if r["id"] in recs:
                dup += 1
            recs[r["id"]] = r
            versions[r.get("prompt_version")] = versions.get(r.get("prompt_version"), 0) + 1
        print(f"{f.name}: {n} records")
    out = list(recs.values())
    res = Path(args.results)
    (res / "all_extracted_news.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
    (res / "all_extracted_news.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nMerged {len(out)} unique records ({dup} duplicates dropped) -> {res / 'all_extracted_news.json'} (+ .jsonl)")
    print("prompt versions:", versions, "(should be ONE version; re-run the odd ones if not)")
    if args.input:
        sys.path.insert(0, str(BASE))
        import extract_crime as ec  # noqa: PLC0415
        ids = [ec.article_fields(a, i)[0] for i, (a, _) in enumerate(ec.load_articles(args.input))]
        missing = [i for i in ids if i not in recs]
        print(f"input articles: {len(ids)} | missing: {len(missing)}")
        if missing:
            (res / "missing_ids.txt").write_text("\n".join(missing), encoding="utf-8")
            print(f"missing ids saved to {res / 'missing_ids.txt'} (re-run those slices; they resume)")


if __name__ == "__main__":
    main()
