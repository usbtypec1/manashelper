import cafeteriaBoss from './assets/achievement-cafeteria-boss.png'
import champion from './assets/achievement-champion.png'
import comeback from './assets/achievement-comeback.png'
import eldinBalasy from './assets/achievement-eldin-balasy.png'
import fall from './assets/achievement-fall.png'
import foodie from './assets/achievement-foodie.png'
import formulaOne from './assets/achievement-formula-one.png'
import nightOwl from './assets/achievement-night-owl.png'
import onTheEdge from './assets/achievement-on-the-edge.png'
import seller from './assets/achievement-seller.png'

// Sprite cells follow the fixed 4 × 3 atlas; individual images override earned/revealed art.
export const achievementArt: Record<string, { cell: number; color: string; image?: string }> = {
  night_owl: { cell: 0, color: '#c6b4ed', image: nightOwl },
  foodie: { cell: 1, color: '#f5bea6', image: foodie },
  cafeteria_boss: { cell: 2, color: '#b4dcca', image: cafeteriaBoss },
  formula_one: { cell: 3, color: '#9dc9f5', image: formulaOne },
  champion: { cell: 4, color: '#f3d18b', image: champion },
  comeback: { cell: 5, color: '#a8dfdb', image: comeback },
  fall: { cell: 6, color: '#f2b0aa', image: fall },
  seller: { cell: 7, color: '#cdb9ea', image: seller },
  eldin_balasy: { cell: 9, color: '#edd6ae', image: eldinBalasy },
  thin_ice: { cell: 10, color: '#add7f0', image: onTheEdge },
}
