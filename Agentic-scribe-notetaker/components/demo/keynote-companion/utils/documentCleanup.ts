/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

const conversationalTailPatterns = [
  /\bwould you like\b/i,
  /\bdo you want\b/i,
  /\bwhat do you think\b/i,
  /\bwhat thoughts\b/i,
  /\bwe could\b/i,
  /\bperhaps\b/i,
  /\bmaybe\b/i,
  /\bi can\b/i,
  /\bi've\b/i,
  /\bit sounds like\b/i,
];

const splitParagraphs = (content: string) =>
  content.replace(/\r\n/g, '\n').split(/\n{2,}/);

const isConversationalTail = (paragraph: string) => {
  const normalized = paragraph.trim();
  if (!normalized) return false;
  if (/^>\s/.test(normalized) || /^#{1,6}\s/.test(normalized)) return false;
  if (!/[?!.]$/.test(normalized)) return false;
  return conversationalTailPatterns.some(pattern => pattern.test(normalized));
};

export const cleanDocumentContent = (content: string) => {
  const paragraphs = splitParagraphs(content);
  let removed = 0;

  while (paragraphs.length > 1 && isConversationalTail(paragraphs[paragraphs.length - 1])) {
    paragraphs.pop();
    removed += 1;
  }

  return {
    content: paragraphs.join('\n\n').trimEnd(),
    removedConversationalBlocks: removed,
  };
};

export const requiresFreshSearchForUserRequest = (request?: string) => {
  const text = request?.toLowerCase() || '';
  if (!text.trim()) return false;
  return (
    /\b(exact|direct|verbatim)\s+quotes?\b/.test(text) ||
    /\bquotes?\b/.test(text) ||
    /\bcitations?\b/.test(text) ||
    /\bcite\b/.test(text) ||
    /\bsources?\b/.test(text) ||
    /\bverify\b/.test(text) ||
    /\bfact[- ]?check\b/.test(text)
  );
};
