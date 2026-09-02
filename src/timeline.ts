export const FPS = 30;

export const TIMELINE = {
  q1: {start: 0, duration: 6.2},
  a1: {start: 6.2, duration: 2.6},
  q2: {start: 8.8, duration: 6.2},
  a2: {start: 15, duration: 2.6},
  q3: {start: 17.6, duration: 6.2},
  hold: {start: 23.8, duration: 3.8},
  cta: {start: 27.6, duration: 4},
} as const;

export const TOTAL_FRAMES = Math.round(31.6 * FPS);
export const REVIEW_FRAMES = Math.round(13.4 * FPS);
