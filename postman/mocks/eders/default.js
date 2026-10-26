// Local contract fixture based on eders.py and anonymous tests/fixtures/eders markup.
// Deliberately accepts only fake credentials. Never connects to OBIS or Eders.
const http = require('http');
const fs = require('fs');
const path = require('path');
const fixtures = path.resolve(__dirname, '../../../tests/fixtures/eders');
const methodname = 'core_course_get_enrolled_courses_by_timeline_classification';
http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://fixture');
  const send = (status, body, headers = {}) => { res.writeHead(status, headers); res.end(body); };
  if (url.pathname === '/site/login') {
    if (req.method === 'GET' && req.headers['x-fixture-mode'] === 'csrf-missing')
      return send(200, '<form></form>');
    if (req.method === 'GET') return send(200, '<form><input name="_csrf" value="fake-csrf"></form>');
    const form = typeof req.body === 'string' ? new URLSearchParams(req.body) : req.body;
    const get = key => form instanceof URLSearchParams ? form.get(key) : form?.[key];
    if (get('LoginForm[username]') !== 'fake-student' || get('LoginForm[password_hash]') !== 'fake-password')
      return send(401, 'Fake credentials required');
    if (req.headers['x-fixture-mode'] === 'login-denied') return send(200, '<form>Invalid login</form>');
    return send(302, '', {location: '/', 'set-cookie': 'obis=fixture; Path=/'});
  }
  const obisPages = {'/vs-ders/taken-grades': 'grades.html', '/vs-ders/taken-lessons': 'attendance.html'};
  if (obisPages[url.pathname]) {
    if (req.method !== 'GET') return send(501, 'Read-only fixture');
    if (!req.headers.cookie?.includes('obis=fixture')) return send(401, 'Login required');
    if (req.headers['x-fixture-mode'] === 'html-error') return send(500, '<h1>Unavailable</h1>');
    return send(200, fs.readFileSync(path.resolve(fixtures, '../obis', obisPages[url.pathname]), 'utf8'),
                {'content-type': 'text/html'});
  }
  if (url.pathname === '/') return send(200, 'Logged in');
  if (url.pathname === '/site/eders')
    return send(302, '', {location: 'https://eders.manas.edu.kg/auth/userkey/login.php?key=fake-sso'});
  if (url.pathname === '/auth/userkey/login.php')
    return send(303, '', {location: '/my/', 'set-cookie': 'MoodleSession=fixture; Path=/'});
  if (url.pathname === '/my/') return send(200, '<a href="/login/logout.php?sesskey=fakekey">Logout</a>');
  if (url.pathname === '/lib/ajax/service.php') {
    const mode = req.headers['x-fixture-mode'];
    if (mode === 'html-error') return send(500, '<h1>Unavailable</h1>');
    if (mode === 'invalid-json') return send(200, '<h1>Unexpected HTML</h1>');
    if (mode === 'expired') return send(302, '', {location: '/login/index.php'});
    const body = req.body;
    if (req.method !== 'POST' || url.searchParams.get('sesskey') !== 'fakekey' ||
        url.searchParams.get('info') !== methodname || !Array.isArray(body) ||
        body[0]?.methodname !== methodname || body[0]?.args?.classification !== 'all' || body[0]?.args?.limit !== 0)
      return send(400, JSON.stringify({error: 'Unexpected contract'}));
    const offset = body[0].args.offset;
    return send(200, JSON.stringify([{data: {courses: offset ? [] : [{id: 10, fullname: 'Fixture course'}], nextoffset: 1}}]),
                {'content-type': 'application/json'});
  }
  const pages = {'/user/profile.php': 'profile.html', '/course/view.php': 'course.html',
                 '/mod/assign/view.php': 'assignment.html', '/mod/quiz/view.php': 'quiz.html'};
  if (req.method === 'GET' && pages[url.pathname])
    return send(200, fs.readFileSync(path.join(fixtures, pages[url.pathname]), 'utf8'), {'content-type': 'text/html'});
  send(501, 'Endpoint outside this fixture contract');
}).listen(process.env.PORT || 4500);
