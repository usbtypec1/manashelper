// Local contract fixture based on the Moodle form and anonymous tests/fixtures/eders markup.
// Deliberately accepts only fake credentials. Never connects to OBIS or Eders.
const http = require('http');
const fs = require('fs');
const path = require('path');
const fixtures = path.resolve(__dirname, '../../../tests/fixtures/eders');
const methodname = 'core_course_get_enrolled_courses_by_timeline_classification';
const completionMethod = 'core_completion_update_activity_completion_status_manually';
let challengeSequence = 0;
const submittedByFlow = new Map();
const browserKeys = new Set();
let browserKeySequence = 0;
const loginPage = (csrf, error = '') => '<form action="/site/login" method="post">' +
  '<input name="_csrf" value="' + csrf + '"><input name="LoginForm[username]">' +
  '<img id="loginform-verifycode-image" src="/site/captcha?v=' + csrf + '">' +
  '<div class="field-loginform-verifycode"><div class="invalid-feedback">' + error + '</div></div></form>' +
  '<script>yii.validation.captcha(value, messages, {"hash":3347,"caseSensitive":false});</script>';
const hasObisSession = req => /(?:^|; )obis=(fixture|rotated)(?:;|$)/.test(req.headers.cookie || '');

http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://fixture');
  const send = (status, body, headers = {}) => { res.writeHead(status, headers); res.end(body); };
  if (url.pathname === '/site/login') {
    const mode = req.headers['x-fixture-mode'];
    if (req.method === 'GET' && mode === 'csrf-missing') return send(200, '<form></form>');
    if (req.method === 'GET') {
      const challenge = 'form-' + (++challengeSequence);
      return send(200, loginPage(challenge), {'set-cookie': 'obis_form=' + challenge + '; Path=/'});
    }
    const form = typeof req.body === 'string' ? new URLSearchParams(req.body) : req.body;
    const get = key => form instanceof URLSearchParams ? form.get(key) : form?.[key];
    const csrf = get('_csrf');
    if (!csrf || !req.headers.cookie?.includes('obis_form=' + csrf))
      return send(400, 'Fresh CSRF and form cookie required');
    if (get('LoginForm[username]') !== 'fake-student' || get('LoginForm[password_hash]') !== 'fake-password')
      return send(200, loginPage(csrf));
    if (['login-denied', 'both-logins-denied'].includes(mode)) return send(200, loginPage(csrf));
    const flow = req.headers['x-fixture-flow'] || mode;
    const submissions = (submittedByFlow.get(flow) || 0) + 1;
    submittedByFlow.set(flow, submissions);
    if (get('LoginForm[verifyCode]') !== 'qinug' || mode === 'captcha-rejected' ||
        (mode === 'captcha-fifth-success' && submissions < 5))
      return send(200, loginPage(csrf, 'Invalid captcha'));
    return send(302, '', {location: '/', 'set-cookie': 'obis=fixture; Path=/'});
  }
  if (url.pathname === '/site/captcha') {
    if (!req.headers.cookie?.includes('obis_form=' + url.searchParams.get('v')))
      return send(400, 'Captcha form cookie required');
    return send(200, fs.readFileSync(path.resolve(fixtures, '../obis/auto-captcha.png')), {'content-type': 'image/png'});
  }
  if (url.pathname === '/site/eders') {
    if (!hasObisSession(req)) return send(302, '', {location: '/site/login'});
    if (req.headers['x-fixture-mode'] === 'browser-login') {
      const key = 'browser-' + (++browserKeySequence);
      browserKeys.add(key);
      return send(302, '', {location: 'https://eders.manas.edu.kg/auth/userkey/login.php?key=' + key,
                           'set-cookie': 'obis=rotated; Path=/'});
    }
    const destination = 'https://eders.manas.edu.kg/auth/userkey/login.php?key=fake-sso';
    if (req.headers['x-fixture-mode'] === 'eders-sso-link')
      return send(200, '<a href="' + destination + '">Eders</a>');
    return send(302, '', {location: destination});
  }
  if (url.pathname === '/auth/userkey/login.php') {
    if (url.searchParams.get('key')?.startsWith('browser-')) {
      if (!browserKeys.delete(url.searchParams.get('key'))) return send(401, 'Spent fake browser key');
      return send(303, '', {location: '/my/index.php?lang=ru', 'set-cookie': 'MoodleSession=fixture; Path=/; HttpOnly; Secure'});
    }
    if (url.searchParams.get('key') !== 'fake-sso') return send(401, 'Fake SSO key required');
    return send(303, '', {location: '/my/index.php?lang=ru', 'set-cookie': 'MoodleSession=fixture; Path=/'});
  }
  const obisPages = {'/vs-ders/taken-grades': 'grades.html', '/vs-ders/taken-lessons': 'attendance.html', '/vs-ders/transkript-detailed': 'transcript.html'};
  if (obisPages[url.pathname]) {
    if (req.method !== 'GET') return send(501, 'Read-only fixture');
    if (!hasObisSession(req)) return send(302, '', {location: '/site/login'});
    if (req.headers['x-fixture-mode'] === 'html-error') return send(500, '<h1>Unavailable</h1>');
    if (url.pathname === '/vs-ders/transkript-detailed' && req.headers['x-fixture-mode'] === 'transcript-malformed') return send(200, '<table></table>');
    const achievementPage = req.headers['x-fixture-mode'] === 'achievement-progress'
      ? {'/vs-ders/taken-lessons': 'attendance_achievements.html', '/vs-ders/transkript-detailed': 'transcript_achievements.html'}[url.pathname]
      : null;
    return send(200, fs.readFileSync(path.resolve(fixtures, '../obis', achievementPage || obisPages[url.pathname]), 'utf8'),
                {'content-type': 'text/html',
                 ...(req.headers['x-fixture-mode'] === 'cookie-rotation' ? {'set-cookie': 'obis=rotated; Path=/'} : {})});
  }
  if (url.pathname === '/') return send(200, '<form action="/site/logout" method="post"></form>');
  if (url.pathname === '/login/index.php') {
    const mode = req.headers['x-fixture-mode'];
    if (mode === 'eders-login-unavailable') return send(503, 'Moodle login unavailable');
    const loginForm = '<form><input name="username" type="text"><input name="logintoken" value="fake-login-token"></form>';
    if (req.method === 'GET' && url.searchParams.get('loginredirect') === '1') {
      if (['eders-login-denied', 'eders-sso-link', 'both-logins-denied', 'sso-expired'].includes(mode)) return send(200, loginForm);
      return send(303, '', {location: '/my/courses.php'});
    }
    if (req.method === 'GET') return send(200, mode === 'eders-token-missing' ? '<form></form>' : loginForm,
      {'set-cookie': 'MoodleSession=initial; Path=/'});
    const form = typeof req.body === 'string' ? new URLSearchParams(req.body) : req.body;
    const get = key => form instanceof URLSearchParams ? form.get(key) : form?.[key];
    if (req.method !== 'POST' || !req.headers['content-type']?.startsWith('application/x-www-form-urlencoded') ||
        !req.headers.cookie?.includes('MoodleSession=initial') || get('anchor') !== '' ||
        get('logintoken') !== 'fake-login-token' || get('username') !== 'fake-student' || get('password') !== 'fake-password')
      return send(400, 'Unexpected Moodle login contract');
    return send(303, '', {location: '/login/index.php?loginredirect=1', 'set-cookie': 'MoodleSession=fixture; Path=/'});
  }
  if (url.pathname.startsWith('/my/') || url.pathname === '/lib/ajax/service.php' || url.pathname === '/user/profile.php' ||
      url.pathname === '/course/view.php' || url.pathname.startsWith('/mod/')) {
    if (!req.headers.cookie?.includes('MoodleSession=fixture')) return send(401, 'Moodle login required');
  }
  if (url.pathname === '/my/courses.php' || url.pathname === '/my/index.php') {
    if (req.headers['x-fixture-mode'] === 'sso-expired')
      return send(200, '<input name="logintoken"><script>M.cfg = {"sesskey":"fakekey"};</script>');
    return send(200, '<script>M.cfg = {"sesskey":"fakekey"};</script>');
  }
  if (url.pathname === '/lib/ajax/service.php') {
    const mode = req.headers['x-fixture-mode'];
    if (mode === 'html-error') return send(500, '<h1>Unavailable</h1>');
    if (mode === 'invalid-json') return send(200, '<h1>Unexpected HTML</h1>');
    if (mode === 'expired') return send(302, '', {location: '/login/index.php'});
    const body = req.body;
    if (url.searchParams.get('info') === completionMethod) {
      if (req.method !== 'POST' || url.searchParams.get('sesskey') !== 'fakekey' ||
          !req.headers['content-type']?.startsWith('application/json') ||
          !Array.isArray(body) || body.length !== 1 || body[0]?.index !== 0 ||
          body[0]?.methodname !== completionMethod || !['20', '21'].includes(body[0]?.args?.cmid) ||
          typeof body[0]?.args?.completed !== 'boolean')
        return send(400, JSON.stringify({error: 'Unexpected completion contract'}));
      if (mode === 'completion-denied')
        return send(200, JSON.stringify([{error: true, exception: {errorcode: 'nopermissions'}}]));
      if (mode === 'completion-false')
        return send(200, JSON.stringify([{error: false, data: {status: false, warnings: []}}]));
      if (mode === 'completion-expired')
        return send(200, JSON.stringify([{error: true, exception: {errorcode: 'invalidsesskey'}}]));
      return send(200, JSON.stringify([{error: false, data: {status: true, warnings: []}}]),
                  {'content-type': 'application/json'});
    }
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
