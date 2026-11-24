/**
 * Canonical host: https://roveuth.com
 *   www.roveuth.com   -> 301 -> roveuth.com
 *   robinlab.pages.dev -> 301 -> roveuth.com   (exact host only)
 * Path and query are preserved. roveuth.com and every other host (including
 * deployment previews such as <hash>.robinlab.pages.dev) pass straight through.
 */
const CANONICAL = 'roveuth.com';
const REDIRECT_HOSTS = new Set(['www.roveuth.com', 'robinlab.pages.dev']);

export async function onRequest(context) {
  const url = new URL(context.request.url);
  if (REDIRECT_HOSTS.has(url.hostname)) {
    url.protocol = 'https:';
    url.hostname = CANONICAL;
    url.port = '';
    return Response.redirect(url.toString(), 301);
  }
  return context.next();
}
