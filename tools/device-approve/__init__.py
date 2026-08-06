"""Device-Approve v3.0 – Unified ID-basierte Freigabe (Ein-Job-Fast-Path).

Package `tools/device-approve` (Design 05 v3.0, Workflow-05-Optimierung,
Review R01-R08 aufgelöst):
- discovery.py    – Ein-Job-Kern v3.0 (group_by_vps, build_ein_job_remote_cmd,
                    parse_ein_job_output, run_remote_ssh, run_discovery;
                    1 SSH pro VPS, Approve in der Session, kein jq)
- approve_step.py – Approve-only-Library (typ-spezifisch: pairing approve
                    telegram <CODE> vs. devices approve <ID>; wird vom
                    Workflow NICHT mehr aufgerufen – R03-E12)
- approve.py      – CLI-Fassade (--full-run Ein-Job, --discover-only,
                    --summary, lokaler Modus)
- summary.py      – Markdown-Summary aus einheitlichem JSON-Schema (Minor #7)

Import in Scripts (if __name__ == "__main__"):
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  from discovery import ...
"""

__version__ = "3.0.0"
