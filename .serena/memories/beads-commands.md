# Beads Issue Tracking Commands

This project uses beads (bd) for issue tracking. Issue prefix: `lwsd-onepager-weasy`

## Common Commands

```bash
# List issues
bd list                    # All open issues
bd list --all              # Include closed issues
bd ready                   # Show ready-to-work issues (no blockers)

# Create issues
bd create                  # Interactive issue creation
bd create "Title here"     # Quick create with title

# Update issues
bd update <id> --status in_progress
bd update <id> --status closed
bd update <id> --priority high

# View issues
bd show <id>               # Full issue details
bd blocked                 # Show blocked issues

# Dependencies
bd dep add <id> --blocks <other-id>
bd dep remove <id> --blocks <other-id>

# Comments
bd comments <id>           # View comments
bd comments <id> --add "comment text"

# Sync & maintenance
bd sync                    # Sync with remote
bd stats                   # Project statistics
bd doctor                  # Health check
```

## Workflow

1. Create issue with `bd create`
2. Mark as in_progress when starting work
3. Add comments for progress notes
4. Mark as closed when done
5. Sync periodically with `bd sync`
