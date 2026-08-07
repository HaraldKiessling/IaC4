"""Device-Approve v3.3 – Unified ID-basierte Freigabe/Ablehnung (Ein-Job-Fast-Path).

Package `tools/device-approve` (Design 05 v3.0/v3.1/v3.2/v3.3, Workflow-05-Optimierung,
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

v3.3 (Listen-Modus + requestId, 2026-08-07 – Owner-Auftrag „GUID soll in der
Liste stehen"): pro pending device-Eintrag wird AUCH `requestId` (UUID-36)
ausgegeben – die ID, die `openclaw devices approve/reject` erwartet
(pending[].deviceId ist der 64er-PublicKey-Hash, NICHT die Approve-ID;
Quelle: openclaw/openclaw src/infra/device-pairing.types.ts:8-25 +
packages/gateway-protocol/src/schema/devices.ts:17-20, docs/cli/devices.md).
Telegram: "" wenn das pairing-request kein requestId-Feld hat (ID-Feld dort
bleibt `code`). Ephemeritaet: requestId wird pro Pairing-Versuch neu vergeben.

Import in Scripts (if __name__ == "__main__"):
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  from discovery import ...
"""

__version__ = "3.3.0"
