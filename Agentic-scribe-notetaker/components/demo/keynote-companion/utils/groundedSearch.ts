/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import type { GoogleGenAI } from '@google/genai';
import { PLACEHOLDER_DOC } from '../../../../lib/constants';

export type GroundedSearchSource = {
  title: string;
  uri: string;
};

export type GroundedSearchResult = {
  model: string;
  queries: string[];
  sources: GroundedSearchSource[];
  text: string;
};

const GROUNDED_SEARCH_MODELS = [
  'gemini-2.5-flash',
  'gemini-2.5-flash-lite',
  'gemini-2.0-flash',
];
const MAX_CONTEXT_CHARS = 3500;
const SEARCH_RETRY_DELAY_MS = 700;

const normalizeQuery = (query: string, topic?: string) => {
  const cleanedQuery = query.trim();
  if (cleanedQuery) return cleanedQuery;
  const cleanedTopic = topic?.trim();
  if (cleanedTopic) return cleanedTopic;
  return 'current research for this Scribe document';
};

const getDocumentExcerpt = (documentContent?: string) => {
  const cleanedDocument = documentContent?.trim();
  if (!cleanedDocument || cleanedDocument === PLACEHOLDER_DOC) {
    return '(No document content yet.)';
  }
  return cleanedDocument.slice(0, MAX_CONTEXT_CHARS);
};

const getResponseText = (response: any) => {
  if (typeof response?.text === 'string') return response.text;
  const parts = response?.candidates?.[0]?.content?.parts;
  if (!Array.isArray(parts)) return '';
  return parts
    .map((part: any) => (typeof part?.text === 'string' ? part.text : ''))
    .filter(Boolean)
    .join('\n');
};

const getGroundingMetadata = (response: any) =>
  response?.candidates?.[0]?.groundingMetadata ??
  response?.candidates?.[0]?.grounding_metadata ??
  {};

const getSources = (metadata: any): GroundedSearchSource[] => {
  const chunks = metadata?.groundingChunks ?? metadata?.grounding_chunks ?? [];
  const seen = new Set<string>();

  return chunks
    .map((chunk: any) => chunk?.web)
    .filter((web: any) => typeof web?.uri === 'string' && web.uri.trim())
    .map((web: any) => ({
      title: typeof web.title === 'string' && web.title.trim() ? web.title.trim() : web.uri,
      uri: web.uri.trim(),
    }))
    .filter((source: GroundedSearchSource) => {
      if (seen.has(source.uri)) return false;
      seen.add(source.uri);
      return true;
    });
};

const isTransientSearchError = (message: string) =>
  /503|unavailable|high demand|temporar|deadline exceeded|internal error|service/i.test(message);

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

async function generateGroundedSearch(
  ai: GoogleGenAI,
  model: string,
  prompt: string,
) {
  return ai.models.generateContent({
    model,
    contents: prompt,
    config: {
      tools: [{ googleSearch: {} }],
    },
  });
}

export async function runGroundedGoogleSearch(
  ai: GoogleGenAI | null | undefined,
  {
    documentContent,
    originalUserRequest,
    query,
    topic,
    userContext,
  }: {
    documentContent?: string;
    originalUserRequest?: string;
    query: string;
    topic?: string;
    userContext?: string;
  },
): Promise<GroundedSearchResult> {
  if (!ai) {
    throw new Error('Google Search needs a Gemini API key before it can run.');
  }

  const normalizedQuery = normalizeQuery(query, topic);
  const prompt = `Use Google Search to research this for an AI scribe.

Search request:
${normalizedQuery}

Original user request:
${originalUserRequest?.trim() || normalizedQuery}

Writing topic:
${topic?.trim() || 'Not specified'}

User context:
${userContext?.trim() || 'None'}

Current document excerpt:
---
${getDocumentExcerpt(documentContent)}
---

If the search request uses pronouns or generic references such as "this", "it", "the ship", or "a cruise ship", resolve them from the original user request and document context before searching.

Return concise, source-grounded notes the scribe can use. Prefer current facts, dates, names, locations, and concrete contact details. If the search results are thin or only generic information is available, say so plainly.`;

  const failures: string[] = [];
  for (const model of GROUNDED_SEARCH_MODELS) {
    for (let attempt = 1; attempt <= 2; attempt += 1) {
      try {
        const response = await generateGroundedSearch(ai, model, prompt);
        const metadata = getGroundingMetadata(response);
        const queries =
          metadata?.webSearchQueries ??
          metadata?.web_search_queries ??
          [];

        return {
          model,
          queries: Array.isArray(queries) ? queries.filter(Boolean) : [],
          sources: getSources(metadata),
          text: getResponseText(response).trim() || 'Google Search completed, but no summary text was returned.',
        };
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        failures.push(`${model}: ${message}`);
        if (attempt < 2 && isTransientSearchError(message)) {
          await sleep(SEARCH_RETRY_DELAY_MS);
          continue;
        }
        break;
      }
    }
  }

  throw new Error(`Google Search failed across fallback models. ${failures.join(' | ')}`);
}

export function formatGroundedSearchMarkdown(result: GroundedSearchResult) {
  const sourceBlock = result.sources.length
    ? `\n\n### Sources\n${result.sources
      .map((source, index) => `${index + 1}. ${source.title} - ${source.uri}`)
      .join('\n')}`
    : '';

  return `## Google Search Notes\n\n${result.text}${sourceBlock}`;
}
