export type VisualTemplate = 'A' | 'B' | 'C';

export type CandyTheme = {
  label: string;
  eyebrow: string;
  backgroundAsset: string;
  sky: string;
  ambient: string;
  accent: string;
  accent2: string;
  accent3: string;
  ink: string;
  panel: string;
  panelEdge: string;
  panelShadow: string;
  choiceGradients: string[];
};

export const CANDY_THEMES: Record<VisualTemplate, CandyTheme> = {
  A: {
    label: 'Candy Kingdom Quiz Show',
    eyebrow: 'CANDY KINGDOM LIVE',
    backgroundAsset: 'art/candy-kingdom.svg',
    sky: 'linear-gradient(165deg, #28ccec 0%, #6a68ee 37%, #f75ab5 72%, #6d2bc6 100%)',
    ambient: '#75f2ff',
    accent: '#ff4eaa',
    accent2: '#7347e9',
    accent3: '#ffd851',
    ink: '#4a195e',
    panel: 'linear-gradient(152deg, #fffdf1 0%, #fff4ce 50%, #f5d98e 100%)',
    panelEdge: '#f7cf55',
    panelShadow: 'rgba(75, 13, 103, .42)',
    choiceGradients: [
      'linear-gradient(145deg, #ff86cf 0%, #f242a2 56%, #9f31d5 100%)',
      'linear-gradient(145deg, #6df1ff 0%, #20c8e1 55%, #4960e5 100%)',
      'linear-gradient(145deg, #c4f36a 0%, #6ed84b 55%, #24a79f 100%)',
      'linear-gradient(145deg, #ffe477 0%, #ffad3d 56%, #f26054 100%)',
    ],
  },
  B: {
    label: 'Neon Candy Arcade',
    eyebrow: 'NEON CANDY ARCADE',
    backgroundAsset: 'art/neon-candy-arcade.svg',
    sky: 'linear-gradient(158deg, #070824 0%, #11104d 40%, #371063 72%, #071936 100%)',
    ambient: '#51efff',
    accent: '#ff45b9',
    accent2: '#33eaff',
    accent3: '#ffe35b',
    ink: '#f8fdff',
    panel: 'linear-gradient(145deg, rgba(10, 13, 48, .97), rgba(40, 16, 78, .94))',
    panelEdge: '#53efff',
    panelShadow: 'rgba(18, 232, 255, .24)',
    choiceGradients: [
      'linear-gradient(145deg, #54106f 0%, #f23cab 100%)',
      'linear-gradient(145deg, #12337b 0%, #21dce7 100%)',
      'linear-gradient(145deg, #663916 0%, #ffca42 100%)',
      'linear-gradient(145deg, #252071 0%, #8b56ff 100%)',
    ],
  },
  C: {
    label: 'Nostalgic Candy Shop',
    eyebrow: 'THE SWEET SHOPPE',
    backgroundAsset: 'art/nostalgic-candy-shop.svg',
    sky: 'linear-gradient(158deg, #f8d7a8 0%, #e87f82 38%, #bd3e67 71%, #4f2548 100%)',
    ambient: '#ffe1a6',
    accent: '#d83e61',
    accent2: '#1fbab2',
    accent3: '#f0c75b',
    ink: '#4a2433',
    panel: 'linear-gradient(145deg, #fff8e6 0%, #fce7bd 58%, #e8c06b 100%)',
    panelEdge: '#cf9d35',
    panelShadow: 'rgba(72, 20, 43, .42)',
    choiceGradients: [
      'linear-gradient(145deg, #ff8ba9 0%, #d83e61 70%, #8f284e 100%)',
      'linear-gradient(145deg, #74e2d8 0%, #20aaa4 66%, #176c74 100%)',
      'linear-gradient(145deg, #ffd874 0%, #e7a83f 66%, #b76436 100%)',
      'linear-gradient(145deg, #ff9fc9 0%, #e85f98 66%, #9e376d 100%)',
    ],
  },
};

export const normalizeTemplate = (value?: string): VisualTemplate =>
  value === 'B' || value === 'C' ? value : 'A';
