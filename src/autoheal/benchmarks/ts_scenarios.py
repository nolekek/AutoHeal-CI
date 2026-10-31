import os
from typing import List, Dict
from .models import BenchmarkCase

TS_SCENARIO_OFF_BY_ONE = BenchmarkCase(
    id="ts_off_by_one",
    name="TypeScript Off-by-One Array Indexing",
    category="boundary_error",
    bug_description="Off-by-one indexing error in list slicing where page calculation excludes the final element.",
    buggy_code="""export function paginateItems<T>(items: T[], page: number, pageSize: number = 5): T[] {
  /** Paginates an array of items with 1-based page indexing. */
  const startIndex = (page - 1) * pageSize;
  const endIndex = startIndex + pageSize - 1;
  return items.slice(startIndex, endIndex);
}
""",
    test_code="""import { paginateItems } from '../src/ts_off_by_one';

describe('paginateItems', () => {
  it('correctly returns items for the first page', () => {
    const data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    const page1 = paginateItems(data, 1, 5);
    expect(page1).toEqual([1, 2, 3, 4, 5]);
  });

  it('correctly returns items for the second page', () => {
    const data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    const page2 = paginateItems(data, 2, 5);
    expect(page2).toEqual([6, 7, 8, 9, 10]);
  });
});
""",
    expected_fixed_code="""export function paginateItems<T>(items: T[], page: number, pageSize: number = 5): T[] {
  /** Paginates an array of items with 1-based page indexing. */
  const startIndex = (page - 1) * pageSize;
  const endIndex = startIndex + pageSize;
  return items.slice(startIndex, endIndex);
}""",
    target_file=os.path.join("src", "ts_off_by_one.ts"),
    test_file=os.path.join("tests", "ts_off_by_one.test.ts"),
    failing_symbol_name="paginateItems",
    failing_line=5,
    exception_type="AssertionError",
    exception_message="expect(received).toEqual(expected) // deep equality\n\n- Expected  - 1\n+ Received  + 0\n\n  Array [\n    1,\n    2,\n    3,\n    4,\n-   5,\n  ]"
)

TS_SCENARIO_UNDEFINED_PROPERTY = BenchmarkCase(
    id="ts_undefined_property",
    name="TypeScript Undefined Property Access in Nested Profile",
    category="null_pointer",
    bug_description="Accessing nested profile property without optional chaining or null checking causes TypeError on undefined user.",
    buggy_code="""export interface UserProfile {
  avatarUrl?: string;
  bio?: string;
  contact?: {
    email?: string;
    phone?: string;
  };
}

export interface User {
  id: string;
  name: string;
  profile?: UserProfile;
}

export function getUserContactEmail(user?: User): string {
  /** Retrieves user contact email or returns empty string if undefined. */
  return user.profile.contact.email;
}
""",
    test_code="""import { getUserContactEmail, User } from '../src/ts_undefined_property';

describe('getUserContactEmail', () => {
  it('returns email when user and contact profile exist', () => {
    const user: User = {
      id: 'u1',
      name: 'Alice',
      profile: {
        contact: { email: 'alice@example.com' }
      }
    };
    expect(getUserContactEmail(user)).toBe('alice@example.com');
  });

  it('safely returns fallback when user is undefined or profile contact is missing', () => {
    expect(getUserContactEmail(undefined)).toBe('');
    expect(getUserContactEmail({ id: 'u2', name: 'Bob' })).toBe('');
    expect(getUserContactEmail({ id: 'u3', name: 'Charlie', profile: {} })).toBe('');
  });
});
""",
    expected_fixed_code="""export interface UserProfile {
  avatarUrl?: string;
  bio?: string;
  contact?: {
    email?: string;
    phone?: string;
  };
}

export interface User {
  id: string;
  name: string;
  profile?: UserProfile;
}

export function getUserContactEmail(user?: User): string {
  /** Retrieves user contact email or returns empty string if undefined. */
  return user?.profile?.contact?.email ?? '';
}""",
    target_file=os.path.join("src", "ts_undefined_property.ts"),
    test_file=os.path.join("tests", "ts_undefined_property.test.ts"),
    failing_symbol_name="getUserContactEmail",
    failing_line=18,
    exception_type="TypeError",
    exception_message="Cannot read properties of undefined (reading 'profile')"
)

TS_SCENARIO_TYPE_COERCION = BenchmarkCase(
    id="ts_type_coercion",
    name="TypeScript String vs Number Comparison Coercion",
    category="type_error",
    bug_description="Comparing string numbers without numerical coercion causes lexical comparison errors where '100' < '20' evaluates to true.",
    buggy_code="""export function comparePriority(a: string | number, b: string | number): number {
  /** Compares two priority scores or thresholds which may arrive as string or number. */
  if (a < b) {
    return -1;
  }
  if (a > b) {
    return 1;
  }
  return 0;
}
""",
    test_code="""import { comparePriority } from '../src/ts_type_coercion';

describe('comparePriority', () => {
  it('correctly compares numbers', () => {
    expect(comparePriority(10, 20)).toBe(-1);
    expect(comparePriority(20, 10)).toBe(1);
    expect(comparePriority(5, 5)).toBe(0);
  });

  it('correctly compares string-formatted numbers without lexical comparison bug', () => {
    expect(comparePriority('100', '20')).toBe(1);
    expect(comparePriority('20', '100')).toBe(-1);
    expect(comparePriority('42', 42)).toBe(0);
    expect(comparePriority(5, '5')).toBe(0);
  });
});
""",
    expected_fixed_code="""export function comparePriority(a: string | number, b: string | number): number {
  /** Compares two priority scores or thresholds which may arrive as string or number. */
  const numA = Number(a);
  const numB = Number(b);
  if (numA < numB) {
    return -1;
  }
  if (numA > numB) {
    return 1;
  }
  return 0;
}""",
    target_file=os.path.join("src", "ts_type_coercion.ts"),
    test_file=os.path.join("tests", "ts_type_coercion.test.ts"),
    failing_symbol_name="comparePriority",
    failing_line=4,
    exception_type="AssertionError",
    exception_message="expect(received).toBe(expected) // Object.is equality\n\nExpected: 1\nReceived: -1"
)

TS_ALL_SCENARIOS: List[BenchmarkCase] = [
    TS_SCENARIO_OFF_BY_ONE,
    TS_SCENARIO_UNDEFINED_PROPERTY,
    TS_SCENARIO_TYPE_COERCION,
]

TS_SCENARIOS_MAP: Dict[str, BenchmarkCase] = {case.id: case for case in TS_ALL_SCENARIOS}

def get_ts_scenarios() -> List[BenchmarkCase]:
    """Returns the complete corpus of TypeScript benchmark scenarios."""
    return list(TS_ALL_SCENARIOS)

def get_ts_scenario(case_id: str) -> BenchmarkCase:
    """Retrieves a single TypeScript scenario by id or raises KeyError."""
    if case_id not in TS_SCENARIOS_MAP:
        raise KeyError(f"TypeScript scenario '{case_id}' not found in benchmark corpus. Available: {list(TS_SCENARIOS_MAP.keys())}")
    return TS_SCENARIOS_MAP[case_id]
