/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import React from 'react';
import { marked } from 'marked';
import * as htmlToImage from 'html-to-image';
import { jsPDF } from 'jspdf';
import { PLACEHOLDER_DOC } from '../../../../lib/constants';
import { Insert } from '../../../../lib/state';
import { sanitizeHtml } from '../../../../lib/safe-html';
import { protectLatex, restoreLatex, stripLeadingWhitespace } from '../utils/markdown';

type UseDownloadActionsArgs = {
  documentContent: string;
  inserts: Insert[];
  setDownloadMenuOpen: (target: 'editor' | 'rendered' | null) => void;
  setPdfStatus: (status: 'idle' | 'preparing' | 'generating') => void;
  topic?: string;
};

export function useDownloadActions({
  documentContent,
  inserts,
  setDownloadMenuOpen,
  setPdfStatus,
  topic,
}: UseDownloadActionsArgs) {
  const handleDownloadAs = (ext: 'md' | 'txt' | 'html') => {
    if (!documentContent || documentContent === PLACEHOLDER_DOC) return;
    const mimeMap: Record<typeof ext, string> = {
      md: 'text/markdown',
      txt: 'text/plain',
      html: 'text/html',
    };
    const filename = `${topic || 'scribe-document'}.${ext}`;
    const blob = new Blob([documentContent], { type: `${mimeMap[ext]};charset=utf-8` });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setDownloadMenuOpen(null);
  };

  const handleDownloadPDF = async (
    ref: React.RefObject<HTMLDivElement>,
    defaultFilename: string,
  ) => {
    if (!ref.current) return;

    setPdfStatus('preparing');
    const element = ref.current;

    const originalStyle = {
      height: element.style.height,
      overflow: element.style.overflow,
      maxHeight: element.style.maxHeight,
      backgroundColor: element.style.backgroundColor,
      color: element.style.color,
      position: element.style.position,
    };

    element.style.height = 'auto';
    element.style.overflow = 'visible';
    element.style.maxHeight = 'none';
    element.style.backgroundColor = '#ffffff';
    element.style.color = '#000000';
    element.style.position = 'relative';
    element.style.setProperty('--theme-bg', '#ffffff');
    element.style.setProperty('--theme-text', '#000000');

    const iframes = element.querySelectorAll('iframe');
    const iframePlaceholders: { iframe: HTMLIFrameElement; placeholder: HTMLDivElement }[] = [];

    iframes.forEach((iframe) => {
      const parentWrapper = iframe.closest('.map-wrapper') as HTMLElement;
      if (parentWrapper) {
        parentWrapper.style.border = 'none';
      }

      const src = iframe.getAttribute('src') || '';
      let locationName = 'Map Location';

      try {
        const url = new URL(src);
        const q = url.searchParams.get('q');
        if (q) locationName = decodeURIComponent(q);
      } catch (e) {
        // Fallback to generic name.
      }

      const placeholder = document.createElement('div');
      placeholder.className = 'map-pdf-placeholder';
      placeholder.style.position = 'absolute';
      placeholder.style.top = '0';
      placeholder.style.left = '0';
      placeholder.style.width = '100%';
      placeholder.style.height = '100%';
      placeholder.style.backgroundColor = '#f1f3f4';
      placeholder.style.border = '1px solid #dadce0';
      placeholder.style.borderRadius = '8px';
      placeholder.style.display = 'flex';
      placeholder.style.flexDirection = 'column';
      placeholder.style.alignItems = 'center';
      placeholder.style.justifyContent = 'center';
      placeholder.style.gap = '12px';
      placeholder.style.color = '#3c4043';
      placeholder.style.fontFamily = 'var(--font-document)';
      placeholder.style.zIndex = '1';

      placeholder.innerHTML = `
        <span class="material-symbols-outlined" style="font-size: 48px; color: #ea4335;">location_on</span>
        <div style="font-weight: 500; font-size: 16px; text-align: center; padding: 0 20px;">${locationName}</div>
        <div style="font-size: 12px; color: #70757a;">Interactive Map (See Online Version)</div>
      `;

      iframe.style.display = 'none';
      iframe.parentNode?.insertBefore(placeholder, iframe);
      iframePlaceholders.push({ iframe, placeholder });
    });

    await new Promise(resolve => setTimeout(resolve, 300));
    setPdfStatus('generating');

    try {
      const width = element.scrollWidth;
      const height = element.scrollHeight;

      const dataUrl = await htmlToImage.toJpeg(element, {
        quality: 0.95,
        pixelRatio: 2,
        backgroundColor: '#ffffff',
        cacheBust: true,
        width,
        height,
        filter: (node) => {
          if (node instanceof HTMLElement) {
            return !node.classList.contains('exclude-from-pdf');
          }
          return true;
        },
      });

      const img = new Image();
      img.src = dataUrl;
      await new Promise(resolve => {
        img.onload = resolve;
        img.onerror = resolve;
      });

      const pdf = new jsPDF({
        orientation: width > height ? 'l' : 'p',
        unit: 'px',
        format: [width, height],
      });

      pdf.addImage(dataUrl, 'JPEG', 0, 0, width, height);
      pdf.save(`${defaultFilename.replace(/\s/g, '_')}.pdf`);
    } catch (error) {
      console.error('PDF generation failed:', error);
    } finally {
      element.style.height = originalStyle.height;
      element.style.overflow = originalStyle.overflow;
      element.style.maxHeight = originalStyle.maxHeight;
      element.style.backgroundColor = originalStyle.backgroundColor;
      element.style.color = originalStyle.color;
      element.style.position = originalStyle.position;
      element.style.removeProperty('--theme-bg');
      element.style.removeProperty('--theme-text');

      iframePlaceholders.forEach(({ iframe, placeholder }) => {
        iframe.style.display = '';
        const parentWrapper = iframe.closest('.map-wrapper') as HTMLElement;
        if (parentWrapper) {
          parentWrapper.style.border = '';
        }
        placeholder.remove();
      });

      setPdfStatus('idle');
    }
  };

  const getRenderedHtmlString = (
    docContent: string,
    currentInserts: Insert[],
  ): string => {
    if (!docContent || docContent === PLACEHOLDER_DOC) return '';

    let processedContent = docContent;
    const tagRegex = /\[(illustration|graph)\s/g;
    let match;
    const foundTags: { start: number; end: number; type: string; fullMatch: string }[] = [];

    while ((match = tagRegex.exec(docContent)) !== null) {
      let inQuotes = false;
      let quoteChar = '';
      let tagEnd = -1;
      const type = match[1];

      for (let i = match.index; i < docContent.length; i++) {
        const char = docContent[i];
        if ((char === '"' || char === "'") && (i === 0 || docContent[i - 1] !== '\\')) {
          if (!inQuotes) {
            inQuotes = true;
            quoteChar = char;
          } else if (char === quoteChar) {
            inQuotes = false;
          }
        }
        if (char === ']' && !inQuotes) {
          tagEnd = i;
          break;
        }
      }

      if (tagEnd !== -1) {
        const fullMatch = docContent.substring(match.index, tagEnd + 1);
        foundTags.push({ start: match.index, end: tagEnd, type, fullMatch });
      }
    }

    for (let i = foundTags.length - 1; i >= 0; i--) {
      const { start, end, type, fullMatch } = foundTags[i];

      const getAttr = (tag: string, attr: string) => {
        const regex = new RegExp(`${attr}\\s*=\\s*(["'])((?:\\\\\\1|.)*?)\\1`);
        const match = tag.match(regex);
        return match ? match[2] : null;
      };

      const id = getAttr(fullMatch, 'id');
      const width = getAttr(fullMatch, 'width');
      let replacement = fullMatch;

      if (id) {
        if (type === 'illustration') {
          const insert = currentInserts.find(ins => ins.id === id);
          if (insert?.status === 'done') {
            const style = width
              ? `width: ${width}; max-width: 100%; display: block; margin: 0 auto;`
              : 'max-width: 100%; display: block; margin: 0 auto;';
            replacement = `<img src="data:image/png;base64,${insert.data}" alt="${insert.prompt}" style="${style}" />`;
          } else {
            replacement = `<!-- Image placeholder: ${id} -->`;
          }
        } else if (type === 'graph') {
          replacement = `<div style="padding: 20px; border: 1px dashed #ccc; text-align: center; background: #f9f9f9; border-radius: 8px;">
            <strong>Interactive Graph: ${id}</strong><br/>
            (View in Scribe app for interactive features)
          </div>`;
        }
      } else if (type === 'graph') {
        replacement = `<div style="padding: 20px; border: 1px dashed #ccc; text-align: center; background: #f9f9f9; border-radius: 8px;">
            <strong>Interactive Graph</strong><br/>
            (View in Scribe app for interactive features)
          </div>`;
      }

      processedContent =
        processedContent.substring(0, start) +
        replacement +
        processedContent.substring(end + 1);
    }

    const cleanedWhitespace = stripLeadingWhitespace(processedContent);
    const { protectedText, latexMap } = protectLatex(cleanedWhitespace);
    const rawHtml = marked.parse(protectedText, {
      async: false,
      breaks: true,
    }) as string;
    return sanitizeHtml(restoreLatex(rawHtml, latexMap));
  };

  return {
    getRenderedHtmlString: () => getRenderedHtmlString(documentContent, inserts),
    handleDownloadAs,
    handleDownloadPDF,
  };
}
