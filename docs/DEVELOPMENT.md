# Development

Develop against the current `2.0` branch of
[404404/HardwareStatus](https://github.com/404404/HardwareStatus). The source
tree retains several `hermesstatus` compatibility names; do not rename runtime
interfaces merely because the repository changed name.

## Change discipline

Start from a clean worktree and the current remote base. Keep Client → Device
v2 → Server → single stats projection → UI as the data path. Changes to a
wire field require review across Client validation, Server decoding/model,
persistence, API/schema, UI, tests, and rollback behavior.

Prefer fixed clocks, synthetic counters, and sanitized fixtures. Do not make
tests pass by accepting unknown fields, weakening TLS/SSH checks, hiding a real
fault, or fabricating telemetry.

## Required checks

Run the relevant focused regression first, then the affected suites:

```sh
(cd clients && python3 -m unittest discover)
(cd scripts/tests && python3 -m unittest discover)
(cd server && go test ./...)
(cd server && go test -race ./...)
(cd server && go vet ./...)
(cd server && go build ./...)
node --test web/js/app.test.js
python3 scripts/validate_migration_contracts.py
python3 scripts/check_release_boundaries.py
python3 scripts/check_unifi_static_authority.py
git diff --check
```

Run only the checks relevant to an isolated documentation-only change, but run
the full required gates before a candidate or release change.

## Candidate and review workflow

Commit an auditable diff to a `codex/` task branch and open a Draft PR. Review
the complete diff for data-contract consistency, resource ownership, current
diagnostics, bounds/truncation, credential exposure, and image provenance.
Only GitHub CI builds candidates. A candidate record binds source SHA, Server
digest, Client digest, platform, and (when present) Catalog revision/hash.

Source changes after qualification create a new candidate and invalidate the
old qualification. Keep real-machine evidence separate from offline/CI
evidence; never describe a passing test fixture as a GK50 or RS820 result.

## Documentation

Update English and Chinese documents together when behavior or public
terminology changes. The project is HardwareStatus, while existing runtime
names and GHCR package names remain compatibility contracts until an explicitly
planned migration changes them.
