# Carisma Updater — staged, offline-capable prototype

Status: **experimental branch**. This is a *local command-line foundation*, not yet a
production-ready updater or an authenticated remote management agent. It does
not download code, poll GitHub, update Core B, perform Core failover, or
automatically migrate a running v0.11 installation. No code in this branch is
automatically deployed to the theater.

## Design boundaries

- An operator obtains a **trusted** application ZIP via a private/admin channel
  and verifies its SHA-256 using a value obtained independently of the ZIP.
- `stage` checks that digest, blocks path traversal, rejects local operational
  data/configuration, and extracts to an immutable version directory.
- `activate` requires an explicit command, makes a *private* backup of the
  shared `data/` tree, and changes an atomic `current` symlink.
- If an explicit systemd unit is supplied, the updater stops and starts it;
  a failing start rolls code back to the preceding release. A successful
  `systemctl is-active` check **does not prove application readiness**.
- `rollback` restores the preceding **code** version only. It intentionally
  does **not** overwrite live data with an older database snapshot because
  this could destroy new tickets/scripts or conflict with schema migrations.
  Database rollback must be handled as a separate, coordinated recovery.
- No service control unless `--service` is explicitly supplied, and no
  updates are initiated while a show is live.
- Offline show runtime is independent from this updater. LAN and Internet
  outages must not trigger installation or rollback.

## Layout (new installations only)

```text
/opt/carisma/
  current -> releases/<release>
  releases/<release>/   # application; data symlink points to shared/data
  shared/data/          # production settings, identities, scripts, media
  backups/data-.../     # private, root-readable backups
  previous.json         # prior code version for rollback
```

**Do not run these commands against an existing v0.11 deployment without
first migrating its working directory, systemd unit and persistent data.**
The first prototype intentionally does not migrate that layout. The live
application is unaffected by merely adding this script to the source repository.

## Safe isolated dry run on a disposable machine

Example only, using a ZIP previously downloaded from the official project
repository and an **independently verified** digest. Replace placeholders
before running; do **not** substitute an unverified digest copied from
the same untrusted source as the ZIP.

```sh
python3 carisma_updater.py --home "$HOME/carisma-test" stage \
  --archive "$HOME/Downloads/DisplayControl-main.zip" \
  --sha256 "<64-character verified SHA-256>" --name v0.11-test
python3 carisma_updater.py --home "$HOME/carisma-test" status
python3 carisma_updater.py --home "$HOME/carisma-test" activate --name v0.11-test
python3 "$HOME/carisma-test/current/server.py"
```

When the disposable server is stopped, another staged version can be
activated. For an actual Core the later deployment design should use a unit
whose `WorkingDirectory=/opt/carisma/current` and
`ExecStart=/usr/bin/python3 /opt/carisma/current/server.py ...`.
Do not add `--cluster-config` until coordinator provisioning has been
verified according to `docs/CLUSTER.md`.

## Production prerequisites still to implement

1. A signed release manifest and trusted keys pinned on each Core (hash
   alone protects integrity only when obtained via an independent trusted
   channel).
2. A local management UI with user approval, authentication, audit log,
   progress/error reporting and strict service permissions.
3. Application HTTP health/readiness and schema compatibility gates;
   migration rollback policy and disk-space/backup verification.
4. A cluster-aware maintenance orchestrator: confirm synchronized replicas,
   drain/switch the standby, update and validate one Core, then the other.
   Never allow unrelated updater instances to trigger simultaneous restarts.
5. Resumable offline file transport and verification; retention, restore
   drills and Linux/macOS/real-hardware tests. Avoid granting a web server
   uncontrolled access to systemd or shell execution.

## Verification

```sh
python3 -m unittest discover -s tests -p test_carisma_updater.py -v
```

The test cases cover a GitHub-style wrapper directory, staging/activation,
private data preservation, code rollback, checksum mismatch and invalid ZIP
paths. These tests must be executed on Linux before accepting any update on
the NEXCOM. They do not verify systemd integration or dual-Core behavior.
