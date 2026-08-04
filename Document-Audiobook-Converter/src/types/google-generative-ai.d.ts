// mammoth ships no types for its browser bundle entry point, so declare the
// one call this app makes. The rest of this file used to hand-declare
// '@google/generative-ai' and a global `mammoth` object supplied by a CDN
// <script>; both are gone - mammoth is a real import now, and the
// @google/generative-ai SDK was never imported by any source file.
declare module 'mammoth/mammoth.browser' {
  export interface ExtractRawTextResult {
    value: string;
    messages: any[];
  }
  export function extractRawText(options: { arrayBuffer: ArrayBuffer }): Promise<ExtractRawTextResult>;

  const mammoth: {
    extractRawText: typeof extractRawText;
  };
  export default mammoth;
}
