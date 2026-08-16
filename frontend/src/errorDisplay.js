export function looksLikeHtml(contentType, body) {
  if ((contentType || '').includes('text/html')) return true
  const trimmed = (body || '').trimStart().toLowerCase()
  return trimmed.startsWith('<!doctype') || trimmed.startsWith('<html')
}

export function openHtmlInNewTab(html) {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const win = window.open(url, '_blank')
  if (win) {
    try {
      win.opener = null
    } catch {
      // ignore
    }
  }
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
  return Boolean(win)
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

export function readableErrorPage(status, body, contentType) {
  if (looksLikeHtml(contentType, body)) return body

  let content = body || '(empty response)'
  if ((contentType || '').includes('application/json') || content.trim().startsWith('{') || content.trim().startsWith('[')) {
    try {
      content = JSON.stringify(JSON.parse(body), null, 2)
    } catch {
      // keep raw body
    }
  }

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>HTTP ${status}</title>
  <style>
    body { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; background: #0b1220; color: #e8eef8; margin: 0; padding: 24px; }
    h1 { font-size: 1.1rem; font-weight: 600; margin: 0 0 16px; color: #fecaca; }
    pre { white-space: pre-wrap; word-break: break-word; margin: 0; line-height: 1.45; }
  </style>
</head>
<body>
  <h1>Server error (HTTP ${status})</h1>
  <pre>${escapeHtml(content)}</pre>
</body>
</html>`
}

export async function describeFetchError(res, fallback, { openTab = true } = {}) {
  const contentType = res.headers.get('content-type') || ''
  const body = await res.text()
  const isServerError = res.status >= 500

  if (isServerError && body) {
    const html = readableErrorPage(res.status, body, contentType)
    const opened = openTab ? openHtmlInNewTab(html) : false
    return {
      message: opened
        ? `${fallback} (HTTP ${res.status}). Details opened in a new tab.`
        : `${fallback} (HTTP ${res.status}). Click “View traceback” to inspect.`,
      html,
    }
  }

  let detail = body
  try {
    const json = JSON.parse(body)
    detail = json.detail || json.error || JSON.stringify(json)
  } catch {
    detail = body.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 300)
  }

  return {
    message: detail ? `${fallback}: ${detail}` : `${fallback} (HTTP ${res.status})`,
    html: null,
  }
}
