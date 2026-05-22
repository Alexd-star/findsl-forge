# Git Workflow

This repository is the authoritative working tree for Topic 19 development.

## Rules

- Commit at the end of each coherent milestone.
- Run `scripts/test.ps1` before every commit.
- Use small, descriptive commit messages.
- Create backup bundles after important milestones.

## Recovery

View history:

```powershell
git log --oneline --decorate
```

Restore a specific file from a previous commit:

```powershell
git restore --source <commit> -- path/to/file
```

Create a backup bundle:

```powershell
git bundle create ..\findsl-forge_backup_YYYYMMDD_HHMMSS.bundle --all
```

Clone from a bundle:

```powershell
git clone findsl-forge_backup_YYYYMMDD_HHMMSS.bundle recovered-findsl-forge
```

