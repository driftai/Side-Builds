export function now() {
  return Date.now();
}

export function isApiRequest(req) {
  return String(req.url || '').startsWith('/api/');
}

export function applyApiCors(req, res) {
  if (!isApiRequest(req)) return;
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, X-Member-Id');
  res.setHeader('Access-Control-Max-Age', '600');
}

export function json(res, code, body) {
  const data = JSON.stringify(body);
  res.writeHead(code, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store'
  });
  res.end(data);
}

export async function readBody(req) {
  let body = '';
  for await (const chunk of req) {
    body += chunk;
    if (body.length > 256 * 1024) throw new Error('payload too large');
  }
  return body ? JSON.parse(body) : {};
}
