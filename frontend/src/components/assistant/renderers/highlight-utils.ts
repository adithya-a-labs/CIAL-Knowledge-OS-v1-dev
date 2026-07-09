export function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

export function highlightHtml(value: string, query: string) {
  if (!query.trim()) return escapeHtml(value);
  const pattern = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  return escapeHtml(value).replace(pattern, '<mark data-search-hit="true" class="rounded bg-[#f9e6a5] px-0.5">$1</mark>');
}

export function zoomStyle(zoomLevel: number) {
  return {
    transform: `scale(${zoomLevel})`,
    transformOrigin: 'top left',
    width: `${100 / zoomLevel}%`,
  } as const;
}

function normalize(value: string) {
  return value.toLowerCase().replace(/\s+/g, ' ').trim();
}

export function buildHighlightNeedles(searchQuery: string, highlightText: string) {
  const needles = new Set<string>();
  const normalizedSearch = normalize(searchQuery);
  if (normalizedSearch.length >= 2) needles.add(normalizedSearch);

  const cleanedHighlight = normalize(highlightText);
  if (!cleanedHighlight) return [...needles];

  needles.add(cleanedHighlight.slice(0, 180));
  const words = cleanedHighlight.split(' ').filter(Boolean);
  for (let index = 0; index < words.length; index += 1) {
    const fragment = words.slice(index, index + 8).join(' ').trim();
    if (fragment.length >= 12) {
      needles.add(fragment);
    }
    if (needles.size >= 8) break;
  }

  return [...needles].filter((value) => value.length >= 2);
}

export function clearTextMarks(root: ParentNode) {
  root.querySelectorAll('[data-pdf-highlight="true"], [data-pdf-search="true"]').forEach((node) => {
    if (!(node instanceof HTMLElement)) return;
    node.dataset.pdfHighlight = '';
    node.dataset.pdfSearch = '';
    node.classList.remove('bg-[#f7df79]', 'bg-[#f9e6a5]', 'rounded', 'transition-colors', 'duration-700');
  });
}
