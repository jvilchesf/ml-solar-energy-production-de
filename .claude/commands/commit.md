---
description: Create git commit with conventional message format
argument-hint: [file1] [file2] ... (optional - commits all changes if not specified)
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git add:*), Bash(git commit:*)
---

# Commit: Create Git Commit

## Files to Commit

Files specified: $ARGUMENTS

(If no files specified, will commit all changes)

## Commit Process

### 1. Review Current State

Check git status:
!`git status`

Review changes to commit:
!`git diff HEAD`

If staging specific files, review their changes:
!`git diff HEAD -- $ARGUMENTS`

### 2. Analyze Changes

Examine the diff and determine:

**Type of change:**
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code refactoring
- `docs`: Documentation only
- `test`: Adding or updating tests
- `chore`: Maintenance (deps, config, etc.)
- `perf`: Performance improvement
- `style`: Code style/formatting

**Scope (if applicable):**
- Component or area affected (api, auth, ui, etc.)

**Description:**
- Brief summary of what changed (50 chars or less)
- Use imperative mood ("add" not "added")

**Body (if needed):**
- More detailed explanation
- Why the change was made
- Any important context

**Breaking changes (if any):**
- Note any breaking changes

### 3. Stage Files

If specific files provided:
```bash
git add $ARGUMENTS
```

If no files specified (commit all changes):
```bash
git add .
```

### 4. Create Commit

Using conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

Example:
```
feat(auth): add user authentication system

Implements JWT-based authentication with:
- Login endpoint with credentials validation
- Token generation and verification
- Protected route middleware

Tests added for all auth flows
```

Execute the commit:
```bash
git commit -m "[commit message]"
```

### 5. Confirm Success

Verify commit created:
!`git log -1 --oneline`

Show commit details:
!`git show --stat`

## Output Report

### Commit Created

**Commit Hash**: [hash]

**Commit Message**:
```
[full commit message]
```

**Files Committed**:
- [list of files with change stats]

**Summary**:
- X files changed
- Y insertions(+)
- Z deletions(-)

### Next Steps

Commit successfully created! Next actions:
- Push to remote: `git push`
- Or continue development with next feature

## Notes

- If there are no changes to commit, report this clearly
- If commit fails (e.g., pre-commit hooks), report the error
- Follow the project's commit message conventions
- Include co-author if appropriate:
  ```
  Co-authored-by: Claude <noreply@anthropic.com>
