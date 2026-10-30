// Local synthetic responses from https://core.telegram.org/bots/api, not a live Telegram server.
const http = require('http');
const calls = [];
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
  calls.push({method, chat_id: id, text: data.text, caption: data.caption, photo: data.photo, reply_markup: keyboard});
  if (errors[id]) {
    const [code, description] = errors[id];
    return respond(code, {ok: false, error_code: code, description, ...(code === 429 ? {parameters: {retry_after: 1}} : {})});
  }
  respond(200, {ok: true, result: {
    message_id: calls.length, date: 0, chat: {id, type: 'private'},
    ...(data.text ? {text: data.text} : {}), ...(data.caption ? {caption: data.caption} : {}),
  }});
}).listen(process.env.PORT || 4500);
