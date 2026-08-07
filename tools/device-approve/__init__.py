"""Device-Approve v3.2 – Unified ID-basierte Freigabe/Ablehnung (Ein-Job-Fast-Path).

Package `tools/device-approve` (Design 05 v3.0/v3.1/v3.2, Workflow-05-Optimierung,
Review R01-R08 aufgelöst):
- discovery.py    – Ein-Job-Kern v3.0/v3.2 (group_by_vps, build_ein_job_remote_cmd,
                    parse_ein_job_output, run_remote_ssh, run_discovery;
                    1 SSH pro VPS, Approve ODER Reject in der Session, kein jq;
                    v3.2: REJECT-Marker + REJECT_CMD_TEMPLATES, action-Param)
- approve_step.py – Approve-only-Library (typ-spezifisch: pairing approve
                    telegram <CODE> vs. devices approve <ID>; wird vom
                    Workflow NICHT mehr aufgerufen – R03-E12)
- approve.py      – CLI-Fassade (--full-run Ein-Job, --discover-only,
                    --list-only v3.1, --reject-only v3.2, --summary, --local)
- summary.py      – Markdown-Summary aus einheitlichem JSON-Schema (Minor #7;
                    v3.2: "rejected"-Status)

v3.2 (Reject-Modus, 2026-08-07): `openclaw devices reject <ID>` per SSH
(docker exec im Instanz-Container); NUR device-Requests (kein 'pairing
reject' in der openclaw CLI – empirisch 2026-08-07).

Import in Scripts (if __name__ == "__main__"):
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  from discovery import ...
"""

__version__ = "3.2.0"
