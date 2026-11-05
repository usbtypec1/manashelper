// Sprite cells follow the fixed 4 × 3 atlas; the last cell is the locked medal.
export const achievementArt: Record<string, { cell: number; color: string }> = {
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
}
