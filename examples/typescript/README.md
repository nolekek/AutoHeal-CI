# TypeScript & Jest Example: AutoHeal-CI in Action

This directory contains a minimal TypeScript & Jest project with an intentional undefined-dereference bug in `auth_service.ts`.

## The Defect
`auth_service.test.ts` tests a user object without `roles`:
```typescript
export function hasAdminRole(user: User): boolean {
  return user.roles.includes('admin'); // TypeError if roles is undefined!
}
```

## Running AutoHeal-CI
When triggered in GitHub Actions or via local CLI:
1. `JestLogParser` catches `TypeError: Cannot read properties of undefined (reading 'includes')`.
2. `TypeScriptASTSlicer` slices `hasAdminRole` and the `User` interface using Tree-sitter TypeScript.
3. The Coder-Critic loop replaces the faulty line with optional chaining `user.roles?.includes('admin') ?? false`.
4. Git Worktree verifies Jest output turns 100% green.
5. Step Summary with Mermaid diagram and patch artifact is published.
