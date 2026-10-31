/**
 * User interface definition.
 */
export interface User {
  id: string;
  name: string;
  roles?: string[];
}

/**
 * Checks if a user possesses the administrator role.
 *
 * BUG: Does not check if `user.roles` is undefined.
 * Throws TypeError: Cannot read properties of undefined (reading 'includes')
 */
export function hasAdminRole(user: User): boolean {
  return user.roles.includes('admin');
}

/**
 * Formats a display name for a user.
 */
export function formatDisplayName(user: User): string {
  return `${user.name} (#${user.id})`;
}
