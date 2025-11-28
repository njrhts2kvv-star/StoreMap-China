/// <reference types="vitest" />

import { describe, expect, it } from 'vitest';
import type { Mall } from '../src/types/store';
import { computeMallStatus } from '../src/utils/competition';

const baseMall: Mall = {
  mallId: 'MALL_BASE',
  mallName: 'Base Mall',
  city: '测试市',
  djiOpened: false,
  instaOpened: false,
  djiReported: false,
  djiExclusive: false,
  djiTarget: false,
  status: 'neutral',
};

const makeMall = (override: Partial<Mall>): Mall => ({
  ...baseMall,
  ...override,
  status: override.status ?? 'neutral',
});

describe('computeMallStatus', () => {
  it('returns blocked when djiExclusive is true', () => {
    const mall = makeMall({ djiExclusive: true });
    expect(computeMallStatus(mall)).toBe('blocked');
  });

  it('prefers blocked over captured when both djiExclusive and instaOpened are true', () => {
    const mall = makeMall({ djiExclusive: true, instaOpened: true, djiTarget: true });
    expect(computeMallStatus(mall)).toBe('blocked');
  });

  it('returns captured when Insta is opened and mall is a DJI target', () => {
    const mall = makeMall({ instaOpened: true, djiTarget: true });
    expect(computeMallStatus(mall)).toBe('captured');
  });

  it('returns captured when Insta is opened and mall was DJI reported', () => {
    const mall = makeMall({ instaOpened: true, djiReported: true });
    expect(computeMallStatus(mall)).toBe('captured');
  });

  it('returns captured when Insta is opened and DJI already opened', () => {
    const mall = makeMall({ instaOpened: true, djiOpened: true });
    expect(computeMallStatus(mall)).toBe('captured');
  });

  it('returns blue_ocean when only Insta is opened and DJI has no interest', () => {
    const mall = makeMall({ instaOpened: true });
    expect(computeMallStatus(mall)).toBe('blue_ocean');
  });

  it('returns opportunity when mall is DJI target but neither brand opened', () => {
    const mall = makeMall({ djiTarget: true });
    expect(computeMallStatus(mall)).toBe('opportunity');
  });

  it('returns gap when DJI has presence but Insta has not opened', () => {
    const mall = makeMall({ djiOpened: true });
    expect(computeMallStatus(mall)).toBe('gap');
  });

  it('returns gap when DJI reported but Insta has not opened', () => {
    const mall = makeMall({ djiReported: true });
    expect(computeMallStatus(mall)).toBe('gap');
  });

  it('returns opportunity when DJI target and reported but Insta not opened', () => {
    const mall = makeMall({ djiTarget: true, djiReported: true, instaOpened: false });
    expect(computeMallStatus(mall)).toBe('opportunity');
  });

  it('returns neutral when no competitive signals exist', () => {
    const mall = makeMall({});
    expect(computeMallStatus(mall)).toBe('neutral');
  });
});
