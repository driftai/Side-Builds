/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { AudioLogTabView } from './AudioLogTabView';
import { DocumentTabView } from './DocumentTabView';
import { MinutesTabView } from './MinutesTabView';
import { TranscriptTabView } from './TranscriptTabView';
import { UnidexLogView } from './UnidexLogView';
import { WorkspaceView } from './WorkspaceView';

export function KeynoteContentView(props: any) {
  const {
    mainTab,
    documentTab,
    documentViewProps,
    transcriptViewProps,
    workspaceViewProps,
    unidexLog,
    setUnidexLog,
    minutesViewProps,
    audioLogViewProps,
  } = props;

  return (
    <div className="document-view-container">
      {mainTab === 'document' && (
        <DocumentTabView documentTab={documentTab} {...documentViewProps} />
      )}
      {mainTab === 'workspace' && <WorkspaceView {...workspaceViewProps} />}
      {mainTab === 'transcript' && <TranscriptTabView {...transcriptViewProps} />}
      {mainTab === 'unidex-log' && (
        <UnidexLogView entries={unidexLog} onClear={() => setUnidexLog([])} />
      )}
      {mainTab === 'minutes' && <MinutesTabView {...minutesViewProps} />}
      {mainTab === 'audio-log' && <AudioLogTabView {...audioLogViewProps} />}
    </div>
  );
}
