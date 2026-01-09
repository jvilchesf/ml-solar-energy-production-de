# Planning: Feature Implementation Plan

## Feature Description

$ARGUMENTS

## Determine Feature Name

Based on the feature description above, create a concise kebab-case feature name (e.g., "user-authentication", "payment-processing", "data-export").

**Feature Name**: [create-feature-name]

This will be used for the plan filename: `plans/[feature-name].md`

## Research Process

### 1. Analyze Existing Codebase Patterns

Search for similar implementations:
- Look for comparable features or components
- Identify relevant files and their structure
- Note patterns, conventions, and standards used
- Document reusable code or utilities

### 2. Research External Documentation

If needed, search for:
- Framework best practices
- Library documentation
- Design patterns
- Similar implementations

### 3. Design Implementation Approach

Determine:
- Which files need to be created or modified
- What models/schemas are required
- Which services or utilities are needed
- How this integrates with existing code
- What testing strategy to use

### 4. Break Down Into Tasks

Create detailed, actionable tasks with:
- Specific file paths
- Exact function/class names
- Clear acceptance criteria
- Validation commands

## Output: Create Plan Document

Save plan as: `plans/[feature-name].md` (using the feature name you created above)

**CRITICAL**: Format this plan for ANOTHER AGENT to execute without seeing this conversation.

### Required Plan Sections

#### 1. Overview
- Brief description of the feature
- Key requirements
- Success criteria

#### 2. Relevant Files

List all files to create or modify with:
- Full file paths
- Brief description of changes needed
- Whether creating new or modifying existing

#### 3. Dependencies

- New libraries or tools required
- Existing utilities or services to use
- Any configuration changes needed

#### 4. Step by Step Tasks

For each task, include:
- **Task number and name**
- **File**: Exact path
- **Action**: What to create/modify
- **Details**: Specific implementation guidance
- **Related files**: Other files that might need updates

Example format:
```markdown
### Task 1: Create User Authentication Schema

File: `app/schemas/auth.py` (create new)

Action: Define Pydantic models for authentication

Details:
- Create `UserCredentials` model with email and password fields
- Create `AuthToken` response model with token and expiry
- Include proper type hints and validation rules
- Add docstrings explaining each model
```

#### 5. Testing Strategy

- What tests to create (unit, integration)
- Test file locations
- Key test cases to cover
- Testing approach for the feature

#### 6. Validation Commands

Exact commands to run in order:
```bash
# Linting
[exact lint command]

# Type checking
[exact type check command]

# Tests
[exact test command]

# Any other validation
```

#### 7. Integration Notes

- How this feature connects to existing code
- Any potential breaking changes
- Migration steps if needed
- Documentation updates required

## Confirmation

After creating the plan, confirm:
- ✅ Feature name created: [feature-name]
- ✅ Plan saved to `plans/[feature-name].md`
- ✅ All tasks are explicit with file paths
- ✅ Validation commands are exact
- ✅ Another agent could execute this without context

**Next step**: Run `/execute plans/[feature-name].md` to implement this feature
