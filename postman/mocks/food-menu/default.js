// Anonymous synthetic HTML based on FoodMenuParser's existing selector contract.
const http = require('http');
http.createServer((req, res) => {
  if (req.method !== 'GET' || req.url !== '/menu') {
    res.writeHead(501); return res.end('Outside fixture contract');
  }
  res.writeHead(Number(req.headers['x-fixture-status'] || 200), {'content-type': 'text/html; charset=utf-8'});
  res.end('<div class="container"></div><div class="container">' +
    '<div class="mbr-section-head">Menu</div><div class="mbr-section-head">25.10.2026</div>' +
    '<div class="row mt-2"><div class="item"><img src="https://example.com/soup.jpg">' +
    '<h5 class="item-title">Fixture Soup</h5><h6 class="item-subtitle">150 kcal</h6></div></div></div>');
}).listen(process.env.PORT || 4500);
