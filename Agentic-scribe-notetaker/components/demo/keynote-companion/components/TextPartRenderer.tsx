/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { marked } from 'marked';
import { memo, useEffect, useState } from 'react';
import { protectLatex, restoreLatex, stripLeadingWhitespace } from '../utils/markdown';
import { MathJaxRenderer } from './MathJaxRenderer';

export const TextPartRenderer = memo(({ text }: { text: string }) => {
  const [html, setHtml] = useState('');

  useEffect(() => {
    if (text.trim() === '') {
      setHtml('');
      return;
    }
    const cleanedWhitespace = stripLeadingWhitespace(text);
    const cleanedText = cleanedWhitespace.replace(/\\(\$)/g, '$1');
    const { protectedText, latexMap } = protectLatex(cleanedText);
    const rawHtml = marked.parse(protectedText, {
      async: false,
      breaks: true,
      gfm: true,
    }) as string;
    const finalHtml = restoreLatex(rawHtml, latexMap);
    setHtml(finalHtml);
  }, [text]);

  return <MathJaxRenderer htmlContent={html} />;
});
