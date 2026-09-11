export const FPS = 30;

export const COVER_DURATION_SECONDS = 2;
export const COVER_FRAMES = Math.round(COVER_DURATION_SECONDS * FPS);
export const THUMBNAIL_FRAME = Math.round(COVER_FRAMES / 2);
export const THUMBNAIL_OFFSET_MS = Math.round((THUMBNAIL_FRAME / FPS) * 1000);

export const TIMELINE = {
  cover: {start: 0, duration: COVER_DURATION_SECONDS},
  q1: {start: 2, duration: 6.2},
  a1: {start: 8.2, duration: 2.6},
  q2: {start: 10.8, duration: 6.2},
  a2: {start: 17, duration: 2.6},
  q3: {start: 19.6, duration: 6.2},
  hold: {start: 25.8, duration: 3.8},
  cta: {start: 29.6, duration: 4},
} as const;

export const TOTAL_FRAMES = Math.round(33.6 * FPS);
export const REVIEW_FRAMES = Math.round(15.4 * FPS);
