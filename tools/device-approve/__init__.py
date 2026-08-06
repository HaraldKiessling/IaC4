"""Device-Approve v2.2 – Unified ID-basierte Freigabe (Telegram-Pairing + Device-Approve).

Package `tools/device-approve` (Design 05 v2.2, Minor #8):
- discovery.py    – Discovery-Kern v2.2 (getrennte Quellen pairing list/devices list,
                    Typ-Ableitung aus ID-Format, GITHUB_OUTPUT)
- approve_step.py – Approve-only (typ-spezifisch: pairing approve telegram <CODE>
                    vs. devices approve <ID>, Major #2-Rollen-Trennung)
- approve.py      – CLI-Fassade (--discover-only, --summary, lokaler Modus)
- summary.py      – Markdown-Summary aus einheitlichem JSON-Schema (Minor #7)

Import in Scripts (if __name__ == "__main__"):
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  from discovery import ...
"""

__version__ = "2.2.0"
