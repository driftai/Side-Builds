/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { Modality } from '@google/genai';
import { MutableRefObject, useEffect, useRef } from 'react';
import {
  IMAGE_GENERATION_FALLBACK_MODELS,
  normalizeImageModel,
} from '../../../../lib/constants';
import { Insert } from '../../../../lib/state';

type UseDocumentEnhancementsArgs = {
  documentContent: string;
  setDocumentContent: (content: string | ((prev: string) => string)) => void;
  inserts: Insert[];
  addInsert: (insert: Insert) => void;
  updateInsert: (id: string, updates: Partial<Insert>) => void;
  ai: MutableRefObject<any>;
  imageModel: string;
  imageGenerationEnabled: boolean;
};

const summarizeImageGenerationFailure = (
  attempts: { model: string; error: string }[],
) => {
  const combinedErrors = attempts.map(attempt => attempt.error).join('\n');

  if (/quota|resource_exhausted|billing/i.test(combinedErrors)) {
    return 'Image generation quota is exhausted or not enabled for this API key. Check Gemini image-model quota or billing, then try again.';
  }
  if (/response modalities|does not support.*image|not supported.*image/i.test(combinedErrors)) {
    return 'The selected model does not support image generation.';
  }
  if (/api key|permission|unauthorized|forbidden/i.test(combinedErrors)) {
    return 'The API key is not authorized for image generation.';
  }

  return 'All fallback models failed to generate the image.';
};

export function useDocumentEnhancements({
  documentContent,
  setDocumentContent,
  inserts,
  addInsert,
  updateInsert,
  ai,
  imageModel,
  imageGenerationEnabled,
}: UseDocumentEnhancementsArgs) {
  const generatingIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (documentContent.includes('<div class="map-wrapper"')) {
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = documentContent;
      let modified = false;

      tempDiv.querySelectorAll('.map-wrapper:not([id])').forEach(mapWrapper => {
        mapWrapper.id = `map_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
        modified = true;
      });

      if (modified) {
        setDocumentContent(tempDiv.innerHTML);
      }
    }

    if (documentContent.includes('[graph')) {
      let modified = false;
      let lastIndex = 0;
      let newContent = '';
      const tagStartRegex = /\[graph\s/g;
      let match;

      while ((match = tagStartRegex.exec(documentContent)) !== null) {
        newContent += documentContent.substring(lastIndex, match.index);

        let bracketIndex = -1;
        let inQuotes = false;
        let quoteChar = '';
        for (let i = match.index; i < documentContent.length; i++) {
          const char = documentContent[i];
          if ((char === '"' || char === "'") && (i === 0 || documentContent[i - 1] !== '\\')) {
            if (!inQuotes) { inQuotes = true; quoteChar = char; }
            else if (char === quoteChar) { inQuotes = false; }
          } else if (char === ']' && !inQuotes) {
            bracketIndex = i;
            break;
          }
        }

        if (bracketIndex !== -1) {
          const fullTag = documentContent.substring(match.index, bracketIndex + 1);
          if (!/\sid\s*=\s*(["'])/.test(fullTag)) {
            modified = true;
            const tagContent = fullTag.substring(6, fullTag.length - 1);
            newContent += `[graph id="graph_${Date.now()}_${Math.random().toString(36).substring(2, 5)}"${tagContent}]`;
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
      newContent += documentContent.substring(lastIndex);

      if (modified) {
        setDocumentContent(newContent);
      }
    }

    if (imageGenerationEnabled && documentContent.includes('[illustration')) {
      let modified = false;
      let lastIndex = 0;
      let newContent = '';
      const tagStartRegex = /\[illustration\s/g;
      let match;

      while ((match = tagStartRegex.exec(documentContent)) !== null) {
        newContent += documentContent.substring(lastIndex, match.index);

        let bracketIndex = -1;
        let inQuotes = false;
        let quoteChar = '';
        for (let i = match.index; i < documentContent.length; i++) {
          const char = documentContent[i];
          if ((char === '"' || char === "'") && (i === 0 || documentContent[i - 1] !== '\\')) {
            if (!inQuotes) { inQuotes = true; quoteChar = char; }
            else if (char === quoteChar) { inQuotes = false; }
          } else if (char === ']' && !inQuotes) {
            bracketIndex = i;
            break;
          }
        }

        if (bracketIndex !== -1) {
          const fullTag = documentContent.substring(match.index, bracketIndex + 1);
          if (!/\sid\s*=\s*(["'])/.test(fullTag)) {
            modified = true;
            const tagContent = fullTag.substring(13, fullTag.length - 1);
            newContent += `[illustration id="img_${Date.now()}_${Math.random().toString(36).substring(2, 5)}"${tagContent}]`;
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
      newContent += documentContent.substring(lastIndex);

      if (modified) {
        setDocumentContent(newContent);
      }
    }
  }, [documentContent, imageGenerationEnabled, setDocumentContent]);

  useEffect(() => {
    if (!imageGenerationEnabled) {
      return;
    }

    const tagRegex = /\[illustration\s/g;
    let match;
    const content = documentContent;

    while ((match = tagRegex.exec(content)) !== null) {
      let inQuotes = false;
      let quoteChar = '';
      let tagEnd = -1;
      for (let i = match.index; i < content.length; i++) {
        const char = content[i];
        if ((char === '"' || char === "'") && (i === 0 || content[i - 1] !== '\\')) {
          if (!inQuotes) { inQuotes = true; quoteChar = char; }
          else if (char === quoteChar) { inQuotes = false; }
        } else if (char === ']' && !inQuotes) {
          tagEnd = i;
          break;
        }
      }

      if (tagEnd !== -1) {
        const fullTag = content.substring(match.index, tagEnd + 1);
        const getAttr = (tag: string, attr: string) => {
          const regex = new RegExp(`${attr}\\s*=\\s*(["'])((?:\\\\\\1|.)*?)\\1`);
          const match = tag.match(regex);
          return match ? match[2] : null;
        };

        const id = getAttr(fullTag, 'id');
        const prompt = getAttr(fullTag, 'prompt');

        if (id && prompt && !inserts.some(ins => ins.id === id) && !generatingIdsRef.current.has(id)) {
          generatingIdsRef.current.add(id);
          addInsert({ id, prompt, status: 'loading', type: 'image' });

          const attemptImageGeneration = async (id: string, prompt: string, baseModel: string) => {
            if (!ai.current) {
              updateInsert(id, {
                status: 'error',
                error: 'Image generation needs a Gemini API key.',
              });
              generatingIdsRef.current.delete(id);
              return;
            }

            const fallbackChain = [
              normalizeImageModel(baseModel),
              ...IMAGE_GENERATION_FALLBACK_MODELS,
            ];

            const uniqueModelsToTry = Array.from(new Set(fallbackChain));
            const attemptLogs: { model: string; error: string }[] = [];

            for (const currentModel of uniqueModelsToTry) {
              try {
                const modelString = currentModel.toLowerCase();
                const isGemini = modelString.includes('gemini');

                updateInsert(id, {
                  status: 'loading',
                  attempts: [...attemptLogs],
                });

                if (!isGemini) {
                  const response = await (ai.current.models as any).generateImages({
                    model: currentModel,
                    prompt,
                    config: { numberOfImages: 1 },
                  });

                  const imgBytes = response.generatedImages?.[0]?.image?.imageBytes;
                  if (imgBytes) {
                    updateInsert(id, {
                      status: 'done',
                      data: imgBytes,
                      mimeType: 'image/png',
                      attempts: attemptLogs,
                    });
                    generatingIdsRef.current.delete(id);
                    return;
                  }
                  throw new Error('Imagen responded but returned no image bytes.');
                }

                const payload = {
                  model: currentModel,
                  contents: prompt,
                  config: { responseModalities: [Modality.IMAGE] },
                };

                const response = await ai.current.models.generateContent(payload as any);
                const part = response.candidates?.[0]?.content?.parts?.find(
                  (p: any) => p.inlineData && !p.thought,
                );

                if (part?.inlineData) {
                  updateInsert(id, {
                    status: 'done',
                    data: part.inlineData.data,
                    mimeType: part.inlineData.mimeType || 'image/png',
                    attempts: attemptLogs,
                  });
                  generatingIdsRef.current.delete(id);
                  return;
                }
                throw new Error(`Model responded but no image data was found. Finish reason: ${response.candidates?.[0]?.finishReason || 'Unknown'}`);
              } catch (error: any) {
                console.error(`Image generation failed for ${currentModel}:`, error);
                const errorMsg = error?.message || String(error);
                attemptLogs.push({ model: currentModel, error: errorMsg });
              }
            }

            updateInsert(id, {
              status: 'error',
              error: summarizeImageGenerationFailure(attemptLogs),
              attempts: [...attemptLogs],
            });
            generatingIdsRef.current.delete(id);
          };

          attemptImageGeneration(id, prompt, imageModel);
        }
      }
    }
  }, [documentContent, inserts, addInsert, updateInsert, ai, imageModel, imageGenerationEnabled]);
}
