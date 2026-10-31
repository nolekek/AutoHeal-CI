import { hasAdminRole, formatDisplayName } from './auth_service';

describe('auth_service', () => {
  it('formats display name correctly', () => {
    expect(formatDisplayName({ id: '42', name: 'Alice' })).toBe('Alice (#42)');
  });

  it('returns true when user has admin role', () => {
    expect(hasAdminRole({ id: '1', name: 'Root', roles: ['admin', 'viewer'] })).toBe(true);
  });

  it('returns false when user roles array is undefined', () => {
    // Intentional failure without defensive navigation
    expect(hasAdminRole({ id: '2', name: 'Guest' })).toBe(false);
  });
});
