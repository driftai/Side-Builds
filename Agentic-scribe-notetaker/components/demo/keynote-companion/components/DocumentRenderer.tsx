/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { marked, Renderer } from 'marked';
import { memo, useMemo } from 'react';
import { Insert, useSourceStore } from '../../../../lib/state';
import FunctionPlotter from '../FunctionPlotter';
import { evaluateDomain, parseArrayString } from '../utils/document-tags';
import { protectLatex, restoreLatex, stripLeadingWhitespace } from '../utils/markdown';
import { EmbedPortal } from './EmbedPortal';
import { MathJaxRenderer } from './MathJaxRenderer';
import { ResizableImage } from './ResizableImage';

// Custom Markdown renderer: turn [Title](#src:<id>) links into citation chips
// the rendered view's click handler can pick up via data-source-id.
const escapeAttr = (value: string) =>
  value
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

const buildCitationRenderer = (sourceTitlesById: Map<string, string>) => {
  const renderer = new Renderer();
  const baseLink = renderer.link.bind(renderer);
  renderer.link = function ({ href, title, tokens }: any) {
    const text = this.parser.parseInline(tokens);
    const match = typeof href === 'string' && href.match(/^#src:(.+)$/);
    if (match) {
      const sourceId = decodeURIComponent(match[1]);
      const sourceTitle = sourceTitlesById.get(sourceId);
      const missing = !sourceTitle;
      const chipTitle = title || (missing ? `Missing source: ${sourceId}` : `Jump to source: ${sourceTitle}`);
      const chipClass = missing ? 'citation-chip citation-chip-missing' : 'citation-chip';
      const icon = missing ? 'link_off' : 'format_quote';
      return `<button type="button" class="${chipClass}" data-source-id="${escapeAttr(sourceId)}" title="${escapeAttr(chipTitle)}"><span class="icon citation-chip-icon">${icon}</span><span class="citation-chip-text">${text}</span></button>`;
    }
    return baseLink({ href, title, tokens });
  };
  return renderer;
};

export const DocumentRenderer = memo(
  ({
    content,
    inserts,
    imageGenerationEnabled,
    onElementResize,
  }: {
    content: string;
    inserts: Insert[];
    imageGenerationEnabled: boolean;
    onElementResize: (id: string, newWidth: string) => void;
  }) => {
    const sources = useSourceStore(state => state.sources);
    const sourceTitlesById = useMemo(
      () => new Map(sources.map(source => [source.id, source.title])),
      [sources],
    );

    const { html, embeds } = useMemo(() => {
      if (!content) return { html: '', embeds: [] };

      const embeds: {
        type: string;
        id: string;
        width: string | null;
        prompt: string | null;
        part: string;
      }[] = [];

      let processedContent = content;
      const tagRegex = /\[(illustration|graph)\s/g;
      let match;
      const foundTags: {
        start: number;
        end: number;
        type: string;
        fullMatch: string;
      }[] = [];

      while ((match = tagRegex.exec(content)) !== null) {
        let inQuotes = false;
        let quoteChar = '';
        let tagEnd = -1;
        const type = match[1];

        for (let i = match.index; i < content.length; i++) {
          const char = content[i];
          if ((char === '"' || char === "'") && (i === 0 || content[i - 1] !== '\\')) {
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
          const fullMatch = content.substring(match.index, tagEnd + 1);
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

        let id = getAttr(fullMatch, 'id');
        const width = getAttr(fullMatch, 'width');
        const prompt = getAttr(fullMatch, 'prompt');

        if (!id) {
          id = `gen_${type}_${i}`;
        }

        embeds.push({ type, id, width, prompt, part: fullMatch });
        processedContent =
          processedContent.substring(0, start) +
          `<div id="scribe-embed-${id}" class="scribe-embed-placeholder"></div>` +
          processedContent.substring(end + 1);
      }

      const cleanedWhitespace = stripLeadingWhitespace(processedContent);
      const { protectedText, latexMap } = protectLatex(cleanedWhitespace);
      const rawHtml = marked.parse(protectedText, {
        async: false,
        breaks: true,
        gfm: true,
        renderer: buildCitationRenderer(sourceTitlesById),
      } as any) as unknown as string;
      const finalHtml = restoreLatex(rawHtml, latexMap);

      return { html: finalHtml, embeds: embeds.reverse() };
    }, [content, sourceTitlesById]);

    return (
      <>
        <MathJaxRenderer htmlContent={html} />
        {embeds.map((embed) => (
          <EmbedPortal key={embed.id} id={embed.id} content={content}>
            {embed.type === 'illustration' ? (() => {
              if (!imageGenerationEnabled) {
                return null;
              }
              const insert = inserts.find(ins => ins.id === embed.id);
              if (!insert) {
                return (
                  <div className="illustration-loading" title={`Preparing: ${embed.prompt}`}>
                    <div className="spinner"></div>
                    <span>Preparing image...</span>
                  </div>
                );
              }

              switch (insert.status) {
                case 'loading':
                  return (
                    <div className="illustration-loading" title={`Generating: ${embed.prompt}`}>
                      <div className="spinner"></div>
                      <span>Generating image...</span>
                      {insert.attempts && insert.attempts.length > 0 && (
                        <div className="attempt-logs">
                          {insert.attempts.map((attempt, idx) => (
                            <div key={idx} className="attempt-log-entry">
                              <span className="icon text-xs mr-1 opacity-50">cancel</span>
                              <span className="attempt-model line-through opacity-50 mr-2">
                                {attempt.model}
                              </span>
                            </div>
                          ))}
                          <div className="text-xs text-blue-500 mt-2 animate-pulse">
                            Trying fallback model...
                          </div>
                        </div>
                      )}
                    </div>
                  );
                case 'error':
                  return (
                    <div className="illustration-error">
                      <span className="icon">error</span>
                      <div className="error-text-container">
                        <span className="error-header">Error generating image</span>
                        {insert.error && <span className="error-detail">{insert.error}</span>}

                        {insert.attempts && insert.attempts.length > 0 && (
                          <div className="attempt-logs mode-error">
                            <span className="attempt-logs-title">Fallback Chain Failed:</span>
                            {insert.attempts.map((attempt, idx) => (
                              <div key={idx} className="attempt-log-entry">
                                <span className="attempt-model font-mono">{attempt.model}</span>
                                <span className="attempt-reason">{attempt.error}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                case 'done': {
                  const src = insert.data?.startsWith('data:')
                    ? insert.data
                    : `data:${insert.mimeType || 'image/png'};base64,${insert.data}`;
                  return (
                    <ResizableImage
                      id={embed.id}
                      src={src}
                      alt={insert.prompt}
                      initialWidth={embed.width}
                      onResize={onElementResize}
                    />
                  );
                }
                default:
                  return <span>{embed.part}</span>;
              }
            })() : (() => {
              const getAttr = (tag: string, attr: string) => {
                const regex = new RegExp(`${attr}\\s*=\\s*(["'])((?:\\\\\\1|.)*?)\\1`);
                const match = tag.match(regex);
                return match ? match[2] : null;
              };

              const graphData = {
                title: getAttr(embed.part, 'title')?.replace(/\\(["'])/g, '$1') || 'Graph',
                functions: parseArrayString(getAttr(embed.part, 'functions') || '[]'),
                labels: parseArrayString(getAttr(embed.part, 'labels') || '[]'),
                xDomain: evaluateDomain(getAttr(embed.part, 'xDomain') || '[-10, 10]'),
                yDomain: evaluateDomain(getAttr(embed.part, 'yDomain') || '[-10, 10]'),
                xLabel: getAttr(embed.part, 'xLabel') || 'x',
                yLabel: getAttr(embed.part, 'yLabel') || 'y',
                colors: parseArrayString(getAttr(embed.part, 'colors') || '[]'),
              };

              return (
                <FunctionPlotter
                  id={embed.id}
                  data={graphData}
                  initialWidth={embed.width}
                  onResize={onElementResize}
                />
              );
            })()}
          </EmbedPortal>
        ))}
      </>
    );
  },
);
