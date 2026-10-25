// Synthetic anonymous markup matching parse_timetable_page's existing selector contract.
const http = require('http');
http.createServer((req, res) => {
  if (req.method !== 'GET' || !/^\/department-printer\/\d+$/.test(req.url)) {
    res.writeHead(501); return res.end('Outside fixture contract');
  }
  res.writeHead(Number(req.headers['x-fixture-status'] || 200), {'content-type': 'text/html; charset=utf-8'});
  res.end('<table class="table-bordered"><tr><th>Schedule</th></tr><tr><td>09:00-09:50</td>' +
    '<td><div>CS101 Analysis<br>Fixture Teacher<br>101</div></td><td></td><td></td><td></td><td></td></tr></table>');
}).listen(process.env.PORT || 4500);
