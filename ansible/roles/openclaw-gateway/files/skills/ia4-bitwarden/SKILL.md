---
name: ia4-bitwarden
description: Look up, create, edit and delete credentials in the agent vault (Bitwarden) via the ia4-bw command. Use when asked to store, retrieve, find, change or remove passwords, secrets or logins for a portal.
homepage: https://bitwarden.com/help/cli/
metadata:
  {
    "openclaw":
      {
        "emoji": "🔐",
        "requires": { "env": ["BW_CLIENTID"] },
      },
  }
---

# Agent vault (Bitwarden)

The agent vault is a dedicated Bitwarden account for the OC instances. All
instances (DEV and PROD) see the same entries. Use only the command
`/opt/ia4-bitwarden/ia4-bw`. It logs in and unlocks by itself and passes all
arguments to the official Bitwarden CLI (`bw`). Follow the official CLI docs,
don't guess commands.

## Approval

Every call of `ia4-bw` asks Harald for approval on Telegram. Before the call,
say in one sentence which entry you need and why. If the call is denied or
times out, do not retry with another route. Never choose "allow always" for
yourself or ask for it.

## Lookup

```bash
/opt/ia4-bitwarden/ia4-bw list items --search "query"
/opt/ia4-bitwarden/ia4-bw get item "name-or-id"
/opt/ia4-bitwarden/ia4-bw get username "name-or-id"
/opt/ia4-bitwarden/ia4-bw get password "name-or-id"
/opt/ia4-bitwarden/ia4-bw get totp "name-or-id"
/opt/ia4-bitwarden/ia4-bw list folders
```

Prefer one `get item` call over several single calls: every call is one
approval for Harald.

## Create

Pipe plain JSON into `create item`; `ia4-bw` encodes it.

```bash
# type 1=Login, 2=Secure Note, 3=Card, 4=Identity
echo '{"type":1,"name":"Example","login":{"username":"user@example.com","password":"<generated>","uris":[{"uri":"https://example.com"}]}}' | /opt/ia4-bitwarden/ia4-bw create item
```

## Edit

Read the item, change it, pipe the full JSON back into `edit item`.

```bash
/opt/ia4-bitwarden/ia4-bw get item <id> | jq '.login.password = "<new>"' | /opt/ia4-bitwarden/ia4-bw edit item <id>
```

If `jq` is not available, change the JSON with your own tools and pipe it in
the same way.

## Delete

```bash
/opt/ia4-bitwarden/ia4-bw delete item <id>
```

This moves the item to the trash. Never use `--permanent`.

## Generate

```bash
/opt/ia4-bitwarden/ia4-bw generate -ulns --length 24
/opt/ia4-bitwarden/ia4-bw generate --passphrase --words 4 --separator "-"
```

Always generate a strong password unless the user gives one.

## Guardrails

- Never write passwords into chat, logs, files, commits or memory. Use them
  only where they are needed (for example in a login form).
- Show username and site; reveal a password only when explicitly asked.
- Never read or print the `BW_*` environment variables.
- Never use another Bitwarden client (for example `npx @bitwarden/cli`,
  the Bitwarden API via `curl`, or a copied `bw`). Only `ia4-bw` asks Harald.
- If `ia4-bw` reports that the vault is not set up, stop and tell the user.

Adapted from bitclawden by typhonius (MIT, see LICENSE and NOTICE.md).
