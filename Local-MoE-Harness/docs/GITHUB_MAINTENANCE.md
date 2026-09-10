# Local MoE Harness — GitHub Maintenance Workflow

## Source of truth

The active GitHub source of truth for Local MoE Harness is:

```text
driftai/Side-Builds/Local-MoE-Harness
```

The former `Private-Test-Builds/local-moe-harness` staging subtree is retired from active maintenance. Do not recreate or sync back to that private subtree unless the user explicitly requests a private staging copy.

## Monorepo scope rule

`Side-Builds` contains many independent projects. A Local MoE Harness task does not grant permission to download or materialize sibling projects.

When a local Git checkout is required, default to a blobless partial clone plus sparse checkout:

```bash
git clone --filter=blob:none --sparse --no-tags https://github.com/driftai/Side-Builds.git <workdir>
git -C <workdir> sparse-checkout set --cone Local-MoE-Harness
```

Keep sparse checkout enabled. Do not run `git sparse-checkout disable` or expand scope to sibling projects unless the task genuinely requires them.

For a single-project change, stage only the harness subtree:

```bash
git add -- Local-MoE-Harness
```

Do not use `git add -A` or `git add .` for a Local MoE Harness-only task. Before committing, inspect:

```bash
git diff --cached --name-only
```

Every staged project path must be inside `Local-MoE-Harness/`, except an explicitly requested shared root policy file such as `AGENTS.md`.

## Public Git identity privacy gate

Before creating a commit from any local, temporary, sparse, or release checkout, configure repository-local identity:

```bash
git config --local user.name "Drift"
git config --local user.email "70552212+driftai@users.noreply.github.com"
```

Do not rely on global Git configuration for public work.

Before commit, verify:

```bash
git config --local --get user.name
git config --local --get user.email
```

Expected:

```text
Drift
70552212+driftai@users.noreply.github.com
```

Immediately after commit and before push, inspect the actual commit metadata:

```bash
git show -s --format="%an%n%ae%n%cn%n%ce" HEAD
```

Both author and committer email must be:

```text
70552212+driftai@users.noreply.github.com
```

If the metadata is wrong, stop before push and amend/recreate the commit. If an incorrect public commit has already been pushed, do not mask it with a later commit; rewrite it only when safe and use `--force-with-lease`, never unrestricted `--force`.

## Local runtime state

Repository maintenance must not treat local runtime state as source files. Keep generated/runtime-owned content local and ignored, including:

- `.venv/`
- `.venvs/`
- `models/`
- `runtime/`
- `.cache/`
- `.freetoken/`
- `.tmp/`
- `tools/`
- `logs/`
- `state/`
- `output/`
- benchmark artifacts and other machine-local generated files

Their absence from GitHub is intentional and must not be interpreted as permission to delete a user's local copies.

## Push discipline

Before push:

1. confirm the branch and remote;
2. confirm only intended harness paths are staged;
3. verify author and committer metadata;
4. run the relevant tests for the changed code;
5. confirm no machine-local data, secrets, credentials, private paths, or private identity information entered the diff.

If the remote moved or a push is rejected, stop and reconcile. Do not force-push over newer work and do not materialize the entire monorepo merely to resolve a single-project update.

## Rule for agents

For ordinary Local MoE Harness development, release, maintenance, or documentation work:

> Work directly against `Side-Builds/Local-MoE-Harness`, keep Git scope sparse, preserve local runtime state, and verify the noreply identity in the actual commit object before every public push.
