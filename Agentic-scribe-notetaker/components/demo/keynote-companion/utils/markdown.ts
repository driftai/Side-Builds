/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Temporarily replaces LaTeX expressions with unique placeholders to protect
 * them from the Markdown parser.
 */
export const protectLatex = (
  text: string,
): { protectedText: string; latexMap: string[] } => {
  const latexMap: string[] = [];
  let placeholderIndex = 0;

  const protect = (match: string) => {
    const placeholder = `<mathjax-placeholder id="MATHJAX_PLACEHOLDER_${placeholderIndex++}"></mathjax-placeholder>`;
    latexMap.push(match);
    return placeholder;
  };

  let protectedText = text.replace(/\$\$([\s\S]*?)\$\$/g, protect);
  protectedText = protectedText.replace(/\\\[([\s\S]*?)\\\]/g, protect);
  protectedText = protectedText.replace(/\$([^\s$](?:[^\n$]*?[^~+\-*#\\\s$])?)\$/g, protect);
  protectedText = protectedText.replace(/\\\(([\s\S]*?)\\\)/g, protect);

  return { protectedText, latexMap };
};

/**
 * Restores the original LaTeX expressions from placeholders after Markdown parsing.
 */
export const restoreLatex = (text: string, latexMap: string[]): string => {
  return text.replace(
    /<mathjax-placeholder id="MATHJAX_PLACEHOLDER_(\d+)"><\/mathjax-placeholder>/g,
    (match, index) => {
      const latex = latexMap[parseInt(index, 10)];
      const isBlock = latex.startsWith('$$') || latex.startsWith('\\[');
      const tag = isBlock ? 'div' : 'span';
      return `<${tag} class="mathjax_process">${latex}</${tag}>`;
    },
  );
};

/**
 * Strips leading whitespace from lines that start with a block-level HTML tag.
 */
export const stripLeadingWhitespace = (htmlString: string) => {
  if (!htmlString) return '';
  return htmlString.replace(
    /^\s*(<(?:div|table|p|h[1-6]|ul|ol|li|blockquote|hr|pre|math)[^>]*>)/gm,
    '$1',
  );
};
