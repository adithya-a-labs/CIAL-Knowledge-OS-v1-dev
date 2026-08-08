/**
 * Browser capabilities used by CIAL that differ between secure contexts and
 * intentionally supported HTTP LAN origins.
 */

export function createUuid(): string {
  const cryptoApi = globalThis.crypto;

  if (typeof cryptoApi?.randomUUID === 'function') {
    return cryptoApi.randomUUID();
  }

  if (typeof cryptoApi?.getRandomValues !== 'function') {
    throw new Error('A cryptographically secure random number generator is unavailable.');
  }

  const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;

  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0'));
  return [
    hex.slice(0, 4).join(''),
    hex.slice(4, 6).join(''),
    hex.slice(6, 8).join(''),
    hex.slice(8, 10).join(''),
    hex.slice(10, 16).join(''),
  ].join('-');
}

export function createPrefixedId(prefix: string): string {
  return `${prefix}${createUuid()}`;
}

function copyWithSelectionFallback(text: string): boolean {
  const activeElement = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.setAttribute('aria-hidden', 'true');
  textarea.style.position = 'fixed';
  textarea.style.inset = '0 auto auto -9999px';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);

  try {
    return document.execCommand('copy');
  } finally {
    textarea.remove();
    activeElement?.focus({ preventScroll: true });
  }
}

export async function copyTextToClipboard(text: string): Promise<void> {
  if (typeof navigator.clipboard?.writeText === 'function') {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // Permission and secure-context policies vary by browser; use the
      // user-gesture-compatible selection fallback below.
    }
  }

  if (!copyWithSelectionFallback(text)) {
    throw new Error('Clipboard access is unavailable.');
  }
}
