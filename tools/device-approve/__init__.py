"""Device-Approve v3.5.0 – Unified ID-basierte Freigabe/Ablehnung/Entfernung (Ein-Job-Fast-Path).

Package `tools/device-approve` (Design 05 v3.0/v3.1/v3.2/v3.3/v3.5, Workflow-05-Optimierung,
Review R01-R08 aufgelöst):
- discovery.py    – Ein-Job-Kern v3.0/v3.2/v3.5 (group_by_vps, build_ein_job_remote_cmd,
                    parse_ein_job_output, run_remote_ssh, run_discovery;
                    1 SSH pro VPS, Approve/Reject/Remove in der Session, kein jq;
                    v3.2: REJECT-Marker + REJECT_CMD_TEMPLATES, action-Param;
                    v3.5: REMOVE-Marker + REMOVE_CMD_TEMPLATES, remove matcht
                    paired[].deviceId=64-hex statt pending[].requestId)
- approve_step.py – Approve-only-Library (typ-spezifisch: pairing approve
                    telegram <CODE> vs. devices approve <ID>; wird vom
                    Workflow NICHT mehr aufgerufen – R03-E12)
- approve.py      – CLI-Fassade (--full-run Ein-Job, --discover-only,
                    --list-only v3.1, --reject-only v3.2, --remove-only v3.5,
                    --summary, --local)
- summary.py      – Markdown-Summary aus einheitlichem JSON-Schema (Minor #7;
                    v3.2: "rejected"-Status; v3.5: "removed"-Status)

v3.2 (Reject-Modus, 2026-08-07): `openclaw devices reject <ID>` per SSH
(docker exec im Instanz-Container); NUR device-Requests (kein 'pairing
reject' in der openclaw CLI – empirisch 2026-08-07).

v3.5 (Remove-Modus, 2026-08-07 – Owner-Auftrag 12:14 „mode=remove als
Follow-up-Feature in Workflow 05“, Antwort „2 b“): `openclaw devices remove
<deviceId>` per SSH (docker exec im Instanz-Container); entfernt GEPAARTE
Geraete – matcht Array `paired`, ID-Feld `deviceId` (64-hex Public-Key-Hash;
paired-Eintraege haben KEINE requestId, CLI-Fakt 2026.7.1, e2e-Beleg
'Removed 587758f1…'). NUR device (kein 'pairing remove' in der openclaw CLI
– empirisch 2026-08-07: `openclaw pairing` kennt nur approve|list|help).
Exit-Code-Vertrag: 0 = removed ODER not_found (gruen), 1 = error, 2 = config.

v3.3 (Listen-Modus + requestId, 2026-08-07 – Owner-Auftrag „GUID soll in der
Liste stehen"): pro pending device-Eintrag wird AUCH `requestId` (UUID-36)
ausgegeben – die ID, die `openclaw devices approve/reject` erwartet
(pending[].deviceId ist der 64er-PublicKey-Hash, NICHT die Approve-ID;
Quelle: openclaw/openclaw src/infra/device-pairing.types.ts:8-25 +
packages/gateway-protocol/src/schema/devices.ts:17-20, docs/cli/devices.md).
Telegram: "" wenn das pairing-request kein requestId-Feld hat (ID-Feld dort
bleibt `code`). Ephemeritaet: requestId wird pro Pairing-Versuch neu vergeben.

v3.3.1 (Approve/Reject-Match auf requestId, 2026-08-07 – Bugfix): der
Approve-/Reject-Pfad matchte `"deviceId": "<UUID>"`, aber die UUID-36 steht
in pending[] im Feld `requestId` (deviceId = 64er-Key-Hash) → 7 Runs
lieferten not_found obwohl pending (31165552730/31165829570 et al.). Fix:
device-Matching auf requestId (Remote-grep + entry_matches_id), deviceId als
defensiver Fallback; Listen-Pfad unveraendert.

Import in Scripts (if __name__ == "__main__"):
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  from discovery import ...
"""

__version__ = "3.5.0"
