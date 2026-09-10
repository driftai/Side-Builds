# Repository working rules

## Monorepo checkout and materialization discipline

Treat every top-level project as an independent working scope unless the request is explicitly cross-project.

When a task targets only one subproject, **do not clone, checkout, or materialize sibling subprojects by default**. Prefer direct GitHub file/tree operations when they are sufficient. When local Git access is needed, default to a blobless partial clone plus sparse checkout:

```bash
git clone --filter=blob:none --sparse --no-tags <repo-url> <workdir>
git -C <workdir> sparse-checkout set --cone <requested-project>
```

Keep the partial-clone filter and sparse checkout active. Do not run `git sparse-checkout disable`, recursively checkout sibling projects, or materialize the entire monorepo merely for convenience. Expand sparse scope only when the user's request genuinely requires another project or shared root path.

When editing or publishing one project:

- stage only the requested subtree, for example `git add -- <requested-project>`;
- do not use `git add -A` or `git add .` for a single-project task;
- inspect `git diff --cached --name-only` before commit and require every staged project path to remain inside the requested scope, except explicitly requested shared root policy files;
- treat remote-ahead/rejected push as a stop-and-reconcile condition, not a reason to force-push or materialize the whole repository;
- preserve sparse/partial-clone behavior after the operation.

If full-repository materialization is genuinely required, explain why before doing it. Default to the smallest repository/subtree scope that can safely complete the task.

## Git commit identity and privacy gate

Git commit metadata is part of public repository history. File/privacy scans do not validate commit author or committer metadata.

Before creating any public-facing commit in a local clone, temporary checkout, sparse checkout, worktree, release workspace, or publication branch, configure repository-local identity:

```bash
git config --local user.name "Drift"
git config --local user.email "70552212+driftai@users.noreply.github.com"
```

Do not rely on global Git configuration for public work.

Before commit, require:

```bash
git config --local --get user.name
git config --local --get user.email
```

Expected:

```text
Drift
70552212+driftai@users.noreply.github.com
```

Immediately after creating a commit and **before push**, inspect the actual commit object:

```bash
git show -s --format="%an%n%ae%n%cn%n%ce" HEAD
```

Both author and committer email must be:

```text
70552212+driftai@users.noreply.github.com
```

If incorrect, stop before pushing and amend/recreate the commit. If a bad commit was already pushed, do not hide it with a later commit; rewrite only when safe, preserve the intended tree, and use `--force-with-lease`, never unrestricted `--force`.

Git identity privacy is a release gate, not a cleanup task.

## Local MoE Harness source of truth

The active GitHub source for Local MoE Harness is:

```text
Side-Builds/Local-MoE-Harness
```

Do not recreate or depend on a `Private-Test-Builds/local-moe-harness` staging subtree during ordinary maintenance. Work directly against this public subtree with the sparse-checkout and Git-identity rules above.
