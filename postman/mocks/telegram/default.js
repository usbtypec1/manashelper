// Local synthetic responses from https://core.telegram.org/bots/api, not a live Telegram server.
const http = require('http');
const calls = [];
const failedEdits = new Set();
const failedInlineSends = new Set();
const messages = new Map();
let nextMessageId = 0;
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
    failedEdits.clear();
    failedInlineSends.clear();
    messages.clear();
    nextMessageId = 0;
    return respond(200, {ok: true});
  }
  if (req.method === 'POST' && req.url === '/_fail_edit') {
    failedEdits.add(Number(req.body.chat_id));
    return respond(200, {ok: true});
  }
  if (req.method === 'POST' && req.url === '/_fail_inline') {
    failedInlineSends.add(Number(req.body.chat_id));
    return respond(200, {ok: true});
  }
  const match = req.url.match(/^\/bot[^/]+\/(sendMessage|sendPhoto|sendVideo|sendMediaGroup|sendRichMessage|editMessageReplyMarkup|answerCallbackQuery)$/);
  if (req.method !== 'POST' || !match) return respond(501, {ok: false, description: 'Outside fixture contract'});
  const data = typeof req.body === 'object' && req.body !== null ? req.body : Object.fromEntries(new URLSearchParams(req.body || ''));
  const id = Number(data.chat_id);
  const method = match[1];
  if (method === 'answerCallbackQuery') {
    calls.push({method, callback_query_id: data.callback_query_id, text: data.text, show_alert: data.show_alert});
    return respond(200, {ok: true, result: true});
  }
  if (!id || (method === 'sendMessage' && !data.text) || (method === 'sendPhoto' && !data.photo) || (method === 'sendVideo' && !data.video)) {
    return respond(400, {ok: false, error_code: 400, description: 'Bad Request: missing required field'});
  }
  let keyboard;
  let media;
  try {
    keyboard = typeof data.reply_markup === 'string' ? JSON.parse(data.reply_markup) : data.reply_markup;
    for (const row of keyboard?.inline_keyboard || []) for (const button of row) {
      if (!button.text || [button.url, button.callback_data, button.web_app].filter(Boolean).length !== 1) throw new Error('button type');
      if (button.callback_data && Buffer.byteLength(button.callback_data, 'utf8') > 64) throw new Error('button data');
      if (button.web_app && new URL(button.web_app.url).protocol !== 'https:') throw new Error('web_app url');
    }
    if (method === 'sendMediaGroup') {
      media = typeof data.media === 'string' ? JSON.parse(data.media) : data.media;
      if (!Array.isArray(media) || media.length < 2 || media.length > 10 || keyboard) throw new Error('album');
      if (media.some(item => !['photo', 'video'].includes(item.type) || !item.media)) throw new Error('album item');
    }
  } catch (_) {
    return respond(400, {ok: false, error_code: 400, description: 'Bad Request: invalid reply_markup'});
  }
  calls.push({method, chat_id: id, message_id: data.message_id, text: data.text, caption: data.caption, photo: data.photo, video: data.video, media, reply_markup: keyboard});
  if (method === 'editMessageReplyMarkup') {
    const original = messages.get(`${id}:${data.message_id}`);
    if (original?.remove_keyboard || original?.keyboard) {
      return respond(400, {ok: false, error_code: 400, description: "Bad Request: message can't be edited"});
    }
  }
  if (method === 'sendMessage' && keyboard?.inline_keyboard && failedInlineSends.has(id)) {
    return respond(500, {ok: false, error_code: 500, description: 'Internal Server Error'});
  }
  if (method === 'editMessageReplyMarkup' && failedEdits.has(id)) {
    return respond(500, {ok: false, error_code: 500, description: 'Internal Server Error'});
  }
  if (errors[id]) {
    const [code, description] = errors[id];
    return respond(code, {ok: false, error_code: code, description, ...(code === 429 ? {parameters: {retry_after: 1}} : {})});
  }
  if (method === 'sendMediaGroup') {
    const result = media.map(item => ({
      message_id: ++nextMessageId, date: 0, chat: {id, type: 'private'},
      ...(item.caption ? {caption: item.caption} : {}),
    }));
    calls[calls.length - 1].message_ids = result.map(item => item.message_id);
    return respond(200, {ok: true, result});
  }
  const messageId = method === 'editMessageReplyMarkup' ? Number(data.message_id) : ++nextMessageId;
  calls[calls.length - 1].message_id = messageId;
  messages.set(`${id}:${messageId}`, keyboard || {});
  respond(200, {ok: true, result: {
    message_id: messageId, date: 0, chat: {id, type: 'private'},
    ...(data.text ? {text: data.text} : {}), ...(data.caption ? {caption: data.caption} : {}),
  }});
}).listen(process.env.PORT || 4500);
