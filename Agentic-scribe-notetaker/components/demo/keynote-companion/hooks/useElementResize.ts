/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import React, { useCallback, useRef } from 'react';
import type { UnidexLogEntry } from '../types';

type UseElementResizeArgs = {
  addUnidexLog: (entry: Omit<UnidexLogEntry, 'id' | 'timestamp'>) => void;
  renderedViewRef: React.RefObject<HTMLDivElement>;
  setDocumentContent: (content: string | ((prev: string) => string)) => void;
  pushToHistory: (content: string) => void;
};

export function useElementResize({
  addUnidexLog,
  renderedViewRef,
  setDocumentContent,
  pushToHistory,
}: UseElementResizeArgs) {
  const handleMapResize = useCallback(
    (id: string, newWidth: string, newHeight: string) => {
      addUnidexLog({
        kind: 'document',
        source: 'Document',
        title: 'Map resized',
        detail: `Element: ${id}\nWidth: ${newWidth}\nHeight: ${newHeight}`,
      });

      setDocumentContent(prevContent => {
        pushToHistory(prevContent);
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = prevContent;
        const mapElement = tempDiv.querySelector(`#${id}`);

        if (mapElement && mapElement instanceof HTMLElement) {
          mapElement.style.width = newWidth;
          mapElement.style.height = newHeight;
          mapElement.style.paddingTop = '0';
        }

        return tempDiv.innerHTML;
      });
    },
    [addUnidexLog, pushToHistory, setDocumentContent],
  );

  const resizeTargetRef = useRef<{
    id: string;
    initialWidth: number;
    initialHeight: number;
  } | null>(null);

  const handleRenderedContentMouseUp = useCallback(() => {
    if (resizeTargetRef.current && renderedViewRef.current) {
      const { id, initialWidth, initialHeight } = resizeTargetRef.current;
      const element = renderedViewRef.current.querySelector(`#${id}`);
      if (element) {
        const iframe = element.querySelector('iframe');
        if (iframe) {
          iframe.style.pointerEvents = 'auto';
        }

        const newWidth = (element as HTMLElement).offsetWidth;
        const newHeight = (element as HTMLElement).offsetHeight;
        if (newWidth !== initialWidth || newHeight !== initialHeight) {
          handleMapResize(id, `${newWidth}px`, `${newHeight}px`);
        }
      }
    }
    resizeTargetRef.current = null;
    window.removeEventListener('mouseup', handleRenderedContentMouseUp);
  }, [handleMapResize, renderedViewRef]);

  const handleRenderedContentMouseDown = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const target = e.target as HTMLElement;
      const mapWrapper = target.closest('.map-wrapper');

      if (
        mapWrapper &&
        mapWrapper.id &&
        getComputedStyle(mapWrapper).resize !== 'none'
      ) {
        const iframe = mapWrapper.querySelector('iframe');
        if (iframe) {
          iframe.style.pointerEvents = 'none';
        }

        resizeTargetRef.current = {
          id: mapWrapper.id,
          initialWidth: (mapWrapper as HTMLElement).offsetWidth,
          initialHeight: (mapWrapper as HTMLElement).offsetHeight,
        };
        window.addEventListener('mouseup', handleRenderedContentMouseUp, {
          once: true,
        });
      }
    },
    [handleRenderedContentMouseUp],
  );

  const handleElementResize = useCallback((id: string, newWidth: string) => {
    addUnidexLog({
      kind: 'document',
      source: 'Document',
      title: 'Visual element resized',
      detail: `Element: ${id}\nWidth: ${newWidth}`,
    });
    setDocumentContent(prevContent => {
      pushToHistory(prevContent);

      let lastIndex = 0;
      let newContent = '';
      const tagStartRegex = /\[(illustration|graph)\s/g;
      let match;
      let found = false;

      while ((match = tagStartRegex.exec(prevContent)) !== null) {
        newContent += prevContent.substring(lastIndex, match.index);

        let bracketIndex = -1;
        let inQuotes = false;
        let quoteChar = '';
        for (let i = match.index; i < prevContent.length; i++) {
          const char = prevContent[i];
          if ((char === '"' || char === "'") && (i === 0 || prevContent[i - 1] !== '\\')) {
            if (!inQuotes) { inQuotes = true; quoteChar = char; }
            else if (char === quoteChar) { inQuotes = false; }
          } else if (char === ']' && !inQuotes) {
            bracketIndex = i;
            break;
          }
        }

        if (bracketIndex !== -1) {
          const fullTag = prevContent.substring(match.index, bracketIndex + 1);
          const elementType = match[1];

          if (fullTag.includes(`id="${id}"`)) {
            found = true;
            let tagBody = fullTag.substring(elementType.length + 2, fullTag.length - 1);
            if (tagBody.includes('width=')) {
              tagBody = tagBody.replace(/width="[^"]+"/, `width="${newWidth}"`);
            } else {
              tagBody += ` width="${newWidth}"`;
            }
            newContent += `[${elementType} ${tagBody.trim()}]`;
          } else {
            newContent += fullTag;
          }
          lastIndex = bracketIndex + 1;
          tagStartRegex.lastIndex = lastIndex;
        } else {
          newContent += '[';
          lastIndex = match.index + 1;
          tagStartRegex.lastIndex = lastIndex;
        }
      }
      newContent += prevContent.substring(lastIndex);

      return found ? newContent : prevContent;
    });
  }, [addUnidexLog, pushToHistory, setDocumentContent]);

  return {
    handleElementResize,
    handleRenderedContentMouseDown,
  };
}
