"""Run the whole Python data pipeline (cached or refreshed)."""
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
if (ROOT/".deps").exists():
    sys.path.insert(0,str(ROOT/".deps"))
from hoklab.collect import collect
from hoklab.analyze import build

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--refresh",action="store_true")
    parser.add_argument("--offline",action="store_true",help="Do not make network requests")
    parser.add_argument("--camp",action="store_true")
    parser.add_argument("--prior",type=float,default=20)
    parser.add_argument("--report",action="store_true",help="Also regenerate the Markdown/PDF report and figures")
    args=parser.parse_args()
    import math
    if not math.isfinite(args.prior) or args.prior<=0:
        parser.error("prior must be positive")
    if args.report and args.prior != 20:
        parser.error("The authored report uses prior=20; use --prior 20 --report or revise report wording first")
    if not args.offline:
        collect(refresh=args.refresh,camp=args.camp)
    build(prior=args.prior)
    if args.report:
        from hoklab.report import build_report
        build_report()
