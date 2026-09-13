import { describe, expect, it } from 'vitest';
import { CONFIG } from '../config';

describe('pre-launch order lock', () => {
  it('defaults customer ordering to disabled unless the launch build explicitly opts in', () => {
    expect(CONFIG.ORDERING_ENABLED).toBe(false);
    expect(CONFIG.LAUNCH_MESSAGE).toContain('Launching Soon');
  });
});
