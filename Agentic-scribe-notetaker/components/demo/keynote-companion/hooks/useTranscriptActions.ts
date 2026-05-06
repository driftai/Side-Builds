/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import React, { useEffect } from 'react';
import { blobToBase64, createWavHeader } from '../utils/audio';
import { AudioLogEntry, TranscriptEntry } from '../types';
import type { MainTab } from '../../../../lib/state';

type UseTranscriptActionsArgs = {
  ai: React.MutableRefObject<any>;
  accurateTranscript: string;
  audioLog: AudioLogEntry[];
  current: { name: string };
  mainTab: MainTab;
  setAccurateTranscript: (text: string) => void;
  setCorrectedTranscript: (text: string) => void;
  setIsCorrectingTranscript: (isCorrecting: boolean) => void;
  setIsGeneratingAccurateTranscript: (isGenerating: boolean) => void;
  setTranscript: React.Dispatch<React.SetStateAction<TranscriptEntry[]>>;
  transcript: TranscriptEntry[];
  user: { name?: string };
};

export function useTranscriptActions({
  ai,
  accurateTranscript,
  audioLog,
  current,
  mainTab,
  setAccurateTranscript,
  setCorrectedTranscript,
  setIsCorrectingTranscript,
  setIsGeneratingAccurateTranscript,
  setTranscript,
  transcript,
  user,
}: UseTranscriptActionsArgs) {
  const handleGetMinutes = async () => {
    if (!ai.current) return;
    setIsCorrectingTranscript(true);
    setCorrectedTranscript('Correcting and summarizing...');

    try {
      const fullTranscript = transcript
        .map(t => `${t.speaker}: ${t.text}`)
        .join('\n');
      const prompt = `Please correct any transcription errors in the following conversation and format it as clean, readable meeting minutes. Use markdown for formatting. Transcript:\n\n${fullTranscript}`;
      const response = await ai.current.models.generateContent({
        model: 'gemini-2.0-flash',
        contents: [{ parts: [{ text: prompt }] }],
      });
      const corrected = response.text;
      setCorrectedTranscript(corrected);
    } catch (error) {
      console.error('Error correcting transcript:', error);
      setCorrectedTranscript('Sorry, an error occurred while processing the transcript.');
    } finally {
      setIsCorrectingTranscript(false);
    }
  };

  const handleGetAccurateTranscript = async () => {
    if (!ai.current || audioLog.length === 0) {
      alert("No audio data available to transcribe. Please ensure you've spoken with the agent first.");
      return;
    }
    setIsGeneratingAccurateTranscript(true);

    try {
      const targetSampleRate = 16000;
      const audioBuffers: Int16Array[] = [];
      const logEntries: string[] = [];

      for (let i = 0; i < audioLog.length; i++) {
        const entry = audioLog[i];
        const arrayBuffer = await entry.blob.arrayBuffer();
        let int16Data = new Int16Array(arrayBuffer);

        const isAgent = entry.speaker === current.name;
        if (isAgent) {
          const resampled = new Int16Array(Math.floor(int16Data.length * (16000 / 24000)));
          for (let j = 0; j < resampled.length; j++) {
            resampled[j] = int16Data[Math.floor(j * 1.5)];
          }
          int16Data = resampled;
        }

        audioBuffers.push(int16Data);
        logEntries.push(`Segment ${i + 1}: Speaker=${entry.speaker}, Timestamp=${entry.timestamp.toLocaleTimeString()}`);
      }

      const totalLength = audioBuffers.reduce((acc, buf) => acc + buf.length, 0);
      const combinedInt16 = new Int16Array(totalLength);
      let offset = 0;
      for (const buf of audioBuffers) {
        combinedInt16.set(buf, offset);
        offset += buf.length;
      }

      const wavHeader = createWavHeader(combinedInt16.byteLength, targetSampleRate);
      const wavBlob = new Blob([wavHeader, combinedInt16], { type: 'audio/wav' });
      const base64Audio = await blobToBase64(wavBlob);

      const speakerTimeLog = logEntries.join('\n');

      const response = await ai.current.models.generateContent({
        model: 'gemini-2.0-flash',
        contents: [
          {
            parts: [
              {
                inlineData: {
                  data: base64Audio,
                  mimeType: 'audio/wav',
                },
              },
              {
                text: `
                  TASK: Provide a VERBATIM, HIGHLY ACCURATE transcript of the combined audio provided.

                  SPEAKER-TIME LOG (for reference):
                  ${speakerTimeLog}

                  STRICT RULES:
                  1. DO NOT summarize.
                  2. DO NOT hallucinate or invent dialogue.
                  3. Use the SPEAKER-TIME LOG to help identify who is speaking at different times in the audio.
                  4. Identify speakers as "${user.name || 'User'}" and "${current.name}".
                  5. Format the output as a clean dialogue using Markdown.
                  6. Use DOUBLE LINE BREAKS between each speaker turn to ensure clear separation.
                  7. Format each turn exactly as: **Speaker Name**: Dialogue text here...

                  The audio is a continuous conversation. Transcribe it accurately.
                `.trim(),
              },
            ],
          },
        ],
        config: {
          systemInstruction: 'You are a professional verbatim transcriptionist. You use the provided speaker-time log to accurately attribute speech in the combined audio file. You never invent content not present in the audio.',
          temperature: 0.1,
        },
      });

      if (!response.text) {
        throw new Error('No text returned from model');
      }

      setAccurateTranscript(response.text);
    } catch (error) {
      console.error('Error generating accurate transcript:', error);
      alert('Failed to generate accurate transcript. The audio might be too long or there was a connection issue.');
    } finally {
      setIsGeneratingAccurateTranscript(false);
    }
  };

  const handleReplaceTranscript = () => {
    if (!accurateTranscript) return;

    const lines = accurateTranscript.split('\n').filter(l => l.trim() !== '');
    const newTranscript: TranscriptEntry[] = [];

    lines.forEach(line => {
      const match = line.match(/\*\*(.*?)\*\*:\s*(.*)/);
      if (match) {
        newTranscript.push({
          speaker: match[1],
          text: match[2].trim(),
        });
      }
    });

    if (newTranscript.length > 0) {
      setTranscript(newTranscript);
      setAccurateTranscript('');
    } else {
      alert('Could not parse the accurate transcript structure.');
    }
  };

  useEffect(() => {
    if (mainTab === 'minutes' && transcript.length > 0) {
      handleGetMinutes();
    }
  }, [mainTab, transcript]);

  return {
    handleGetAccurateTranscript,
    handleGetMinutes,
    handleReplaceTranscript,
  };
}
