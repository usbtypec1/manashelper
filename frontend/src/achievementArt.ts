// Earned/revealed art is `assets/achievement-<key with dashes>.png`; a key without one falls back to its
// sprite cell in the fixed 4 × 3 atlas, or to the locked medal (cell 11) when it has no cell either.
const images = import.meta.glob<string>('./assets/achievement-*.png', { eager: true, import: 'default' })

const art: Record<string, { cell?: number; color: string }> = {
  night_owl: { cell: 0, color: '#c6b4ed' },
  foodie: { cell: 1, color: '#f5bea6' },
  cafeteria_boss: { cell: 2, color: '#b4dcca' },
  formula_one: { cell: 3, color: '#9dc9f5' },
  champion: { cell: 4, color: '#f3d18b' },
  comeback: { cell: 5, color: '#a8dfdb' },
  fall: { cell: 6, color: '#f2b0aa' },
  seller: { cell: 7, color: '#cdb9ea' },
  eldin_balasy: { cell: 9, color: '#edd6ae' },
  thin_ice: { cell: 10, color: '#add7f0' },
  phoenix: { color: '#f6b98f' },
  stability: { color: '#bcd9b0' },
  iron_attendance: { color: '#c4ccd6' },
  critic: { color: '#d9b8c4' },
  einstein: { color: '#b8c6f0' },
}

export const achievementArt: Record<string, { cell?: number; color: string; image?: string }> = Object.fromEntries(
  Object.entries(art).map(([key, value]) => [
    key,
    { ...value, image: images[`./assets/achievement-${key.replaceAll('_', '-')}.png`] },
  ]),
)
