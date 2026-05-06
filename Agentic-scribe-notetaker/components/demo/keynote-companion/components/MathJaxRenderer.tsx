/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { memo, useEffect, useMemo, useRef } from 'react';
import { sanitizeHtml } from '../../../../lib/safe-html';

declare const MathJax: any;

/**
 * Renders sanitized HTML content and then applies MathJax typesetting.
 */
export const MathJaxRenderer = memo(({ htmlContent }: { htmlContent: string }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mathJaxPromiseRef = useRef(Promise.resolve());
  const safeHtmlContent = useMemo(
    () => sanitizeHtml(htmlContent),
    [htmlContent],
  );

  useEffect(() => {
    if (safeHtmlContent && containerRef.current) {
      if (typeof MathJax !== 'undefined' && MathJax.typesetPromise) {
        const currentElement = containerRef.current;
        mathJaxPromiseRef.current = mathJaxPromiseRef.current
          .then(() => {
            if (currentElement && currentElement.isConnected) {
              return MathJax.typesetPromise([currentElement]);
            }
          })
          .catch((err: Error) =>
            console.error('MathJax typesetting error:', err),
          );
      }
    }
  }, [safeHtmlContent]);

  return (
    <div
      ref={containerRef}
      className="mathjax_ignore"
      dangerouslySetInnerHTML={{ __html: safeHtmlContent }}
    />
  );
});
