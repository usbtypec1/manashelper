// Local synthetic responses from https://core.telegram.org/bots/api, not a live Telegram server.
const http = require('http');
const calls = [];
const attempts = new Map();
const errors = {
  910002: [403, 'Forbidden: bot was blocked by the user'],
  910003: [403, 'Forbidden: user is deactivated'],
  910004: [400, 'Bad Request: chat not found'],
  910005: [429, 'Too Many Requests: retry after 1'],
  910006: [500, 'Internal Server Error'],
  910007: [400, "Bad Request: can't parse entities"],
};
http.createServer((req, res) => {
  const respond = (status, value) => {
    res.writeHead(status, {'content-type': 'application/json'});
    res.end(JSON.stringify(value));
  };
  if (req.method === 'GET' && req.url === '/_requests') return respond(200, calls);
  if (req.method === 'POST' && req.url === '/_reset') {
    calls.length = 0;
    attempts.clear();
    return respond(200, {ok: true});
  }
  const match = req.url.match(/^\/bot[^/]+\/(sendMessage|sendPhoto|sendRichMessage)$/);
  if (req.method !== 'POST' || !match) return respond(501, {ok: false, description: 'Outside fixture contract'});
  const data = typeof req.body === 'object' && req.body !== null ? req.body : Object.fromEntries(new URLSearchParams(req.body || ''));
  const id = Number(data.chat_id);
  const method = match[1];
  if (!id || (method === 'sendMessage' && !data.text) || (method === 'sendPhoto' && !data.photo)) {
    return respond(400, {ok: false, error_code: 400, description: 'Bad Request: missing required field'});
  }
  let keyboard;
  try {
    keyboard = typeof data.reply_markup === 'string' ? JSON.parse(data.reply_markup) : data.reply_markup;
    for (const row of keyboard?.inline_keyboard || []) for (const button of row) {
      if (!button.text || Boolean(button.url) === Boolean(button.callback_data)) throw new Error('button type');
      if (button.callback_data && Buffer.byteLength(button.callback_data, 'utf8') > 64) throw new Error('button data');
    }
  } catch (_) {
    return respond(400, {ok: false, error_code: 400, description: 'Bad Request: invalid reply_markup'});
  }
  const key = `${id}:${method}`;
  const attempt = (attempts.get(key) || 0) + 1;
  attempts.set(key, attempt);
  calls.push({method, chat_id: id, at: Date.now(), text: data.text, caption: data.caption, photo: data.photo, reply_markup: keyboard});
  if (id === 920005 && attempt === 1) {
    return respond(429, {ok: false, error_code: 429, description: 'Flood control', parameters: {retry_after: 1}});
  }
  if ((id === 920006 || (id === 920008 && method === 'sendMessage')) && attempt === 1) {
    return respond(503, {ok: false, error_code: 503, description: 'Service unavailable'});
  }
  if (id === 920007 && attempt === 1) {
    res.writeHead(502, {'content-type': 'text/html'});
    return res.end('<html>Bad gateway</html>');
  }
  if (errors[id]) {
    const [code, description] = errors[id];
    return respond(code, {ok: false, error_code: code, description, ...(code === 429 ? {parameters: {retry_after: 1}} : {})});
  }
  respond(200, {ok: true, result: {
    message_id: calls.length, date: 0, chat: {id, type: 'private'},
    ...(data.text ? {text: data.text} : {}), ...(data.caption ? {caption: data.caption} : {}),
  }});
}).listen(process.env.PORT || 4500);
