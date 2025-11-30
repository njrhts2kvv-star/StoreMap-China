const clamp = (value: number, min = 0, max = 1) => Math.min(max, Math.max(min, value));

const hexToRgb = (hex: string) => {
  const normalized = hex.replace('#', '');
  const bigint = parseInt(normalized, 16);
  const len = normalized.length === 3 ? 1 : 0;
  if (Number.isNaN(bigint)) return { r: 0, g: 0, b: 0 };
  if (len) {
    const r = (bigint >> 8) & 0xf;
    const g = (bigint >> 4) & 0xf;
    const b = bigint & 0xf;
    return {
      r: (r << 4) | r,
      g: (g << 4) | g,
      b: (b << 4) | b,
    };
  }
  return {
    r: (bigint >> 16) & 255,
    g: (bigint >> 8) & 255,
    b: bigint & 255,
  };
};

const componentToHex = (c: number) => {
  const hex = c.toString(16);
  return hex.length === 1 ? `0${hex}` : hex;
};

const rgbToHex = ({ r, g, b }: { r: number; g: number; b: number }) =>
  `#${componentToHex(r)}${componentToHex(g)}${componentToHex(b)}`;

export const mixColors = (fromHex: string, toHex: string, ratio: number) => {
  const t = clamp(ratio);
  const from = hexToRgb(fromHex);
  const to = hexToRgb(toHex);
  return rgbToHex({
    r: Math.round(from.r + (to.r - from.r) * t),
    g: Math.round(from.g + (to.g - from.g) * t),
    b: Math.round(from.b + (to.b - from.b) * t),
  });
};

export const lighten = (hex: string, amount: number) => {
  const t = clamp(amount);
  const { r, g, b } = hexToRgb(hex);
  return rgbToHex({
    r: Math.round(r + (255 - r) * t),
    g: Math.round(g + (255 - g) * t),
    b: Math.round(b + (255 - b) * t),
  });
};
