export const HOOK_EXPERIMENT_START_DAY = 25;

export type HookExperimentVariant = 'cover-hook' | 'question-first-hook';

/**
 * Controlled opening-hook experiment.
 *
 * Posts before 025 preserve the historical premium-cover treatment. Starting
 * with post 025, variants alternate deterministically so the three daily time
 * slots rotate across A/B instead of permanently tying one variant to one slot.
 */
export const hookExperimentVariant = (day: number): HookExperimentVariant => {
  if (day < HOOK_EXPERIMENT_START_DAY) return 'cover-hook';
  return day % 2 === 0 ? 'question-first-hook' : 'cover-hook';
};
