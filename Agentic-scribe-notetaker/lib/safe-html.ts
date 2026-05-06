/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import DOMPurify from 'dompurify';

const SANITIZE_OPTIONS = {
  ADD_TAGS: ['iframe'],
  ADD_ATTR: [
    'allow',
    'allowfullscreen',
    'class',
    'frameborder',
    'height',
    'id',
    'loading',
    'referrerpolicy',
    'rel',
    'scrolling',
    'src',
    'style',
    'target',
    'title',
    'width',
  ],
  ADD_DATA_URI_TAGS: ['img'],
  FORBID_TAGS: ['script', 'style'],
};

const isAllowedIframeSrc = (src: string): boolean => {
  if (!src || typeof window === 'undefined') return false;

  try {
    const url = new URL(src, window.location.href);
    if (url.protocol !== 'https:') return false;

    return (
      ((url.hostname === 'www.google.com' || url.hostname === 'google.com') &&
        url.pathname.startsWith('/maps')) ||
      url.hostname === 'maps.google.com'
    );
  } catch {
    return false;
  }
};

const hardenSanitizedHtml = (html: string): string => {
  if (typeof document === 'undefined') return html;

  const template = document.createElement('template');
  template.innerHTML = html;

  template.content.querySelectorAll('a[target="_blank"]').forEach((anchor) => {
    anchor.setAttribute('rel', 'noopener noreferrer');
  });

  template.content.querySelectorAll('iframe').forEach((iframe) => {
    const src = iframe.getAttribute('src') || '';
    if (!isAllowedIframeSrc(src)) {
      iframe.remove();
      return;
    }

    iframe.setAttribute('loading', iframe.getAttribute('loading') || 'lazy');
    iframe.setAttribute(
      'referrerpolicy',
      iframe.getAttribute('referrerpolicy') || 'no-referrer-when-downgrade',
    );
  });

  return template.innerHTML;
};

export const sanitizeHtml = (html: string): string => {
  const sanitized = DOMPurify.sanitize(html, SANITIZE_OPTIONS);
  return hardenSanitizedHtml(sanitized);
};
