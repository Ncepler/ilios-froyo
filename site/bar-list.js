// The topping bar as plain text, in the shop's order (for browsers without WebGL). Kept apart from bar.js so the
// fallback does not have to load three.js.
const ZONES = [
  ['Fresh fruit', ['Strawberries', 'Golden Mango', 'Granola (nut free, gluten free)', 'Dates', 'Fresh Figs', 'Raspberry Sauce', 'Kiwi', 'Blueberries', 'Green Grapes', 'Honeydew', 'Coconut', 'Pineapple']],
  ['Candy & crunch', ['Gummy Bears', "M&M's", 'Rainbow Sprinkles', 'Brownie Bites', 'Rainbow Cookies', 'Chocolate Chips', 'Chocolate Sprinkles', 'Rice Krispies Treats', 'Oreo Crumble', 'Mini Cookies', 'Biscoff Cookies', 'Cookie Dough', 'Sour Strips', 'Gummy Worms', 'Chocolate Chunks']],
  ['Warm, from the counter', ['Pistachio Kataifi', 'Nutella', 'Biscoff Cookie Butter', 'Cinnamon Roll', 'Honey', 'Olive Oil + Sea Salt']],
];
export function listHTML() {
  return ZONES.map(([h, items]) => `<div><h3>${h}</h3><ul>${items.map(i => `<li>${i}</li>`).join('')}</ul></div>`).join('');
}
