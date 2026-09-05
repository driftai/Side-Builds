/** Small app-facing facade for hybrid cached/live depth playback. */
import { DepthAheadController } from './depth-ahead-controller.js';
import { installCacheSampling, selectedCacheRate, restoreCacheSampling } from './cache-sampling.js';
import { DepthCacheRecalibrator } from './depth-cache-recalibrator.js';
import { DEPTH_CACHE_PIPELINE_VERSION } from './depth-cache-codec.js';
import { ConversionScoreAccumulator, scoreDepthConversion } from './depth-conversion-score.js';
import { DepthRenderFusion } from './depth-render-fusion.js';
import { DepthCacheLibrary } from './depth-cache-library.js';
import { normalizeConversionFeedback } from './depth-feedback-report.js';
import { restoredProfileState, selectBestResumableProfile } from './depth-profile-resume.js';

export class DepthPlaybackCoordinator {
  constructor(app) {
    this.app = app;
    this.mode = document.getElementById('depthPlaybackMode')?.value === 'live' ? 'live' : 'hybrid';
    this.source = null;
    this.restartTimer = null;
    this.configureGeneration = 0;
    this.lastPairKey = '';
    this.cachedDiagnostic = null;
    this.fusion = new DepthRenderFusion({ mode: document.getElementById('depthFusionMode')?.value });
    this.bundledScore = new ConversionScoreAccumulator();
    this.lastBundledScoreKey = '';
    this.lastBundledScoreFrame = null;
    this.lastBundledScoreGuide = null;
    this.lastHybridScoreKey = '';
    this.lastHybridScoreFrame = null;
    this.lastHybridScoreGuide = null;
    this.controller = new DepthAheadController({
      engine: app.liveDepth,
      onStatus: state => this.renderStatus(state)
    });
    this.controller.setMode(this.mode);
    this.library = new DepthCacheLibrary(this);
    installCacheSampling(this);
    this.renderStatus({ phase: 'idle', message: 'Hybrid cache starts when a live video is imported.' });
  }
  setSystemMemory(systemMemoryGb) {
    this.controller.setMemoryBudgetForSystemRam(systemMemoryGb);
  }
  async setMode(mode) {
    this.mode = mode === 'live' ? 'live' : 'hybrid';
    this.controller.setMode(this.mode);
    this.configureGeneration += 1;
    this.lastPairKey = '';
    this.cachedDiagnostic = null;
    this.app.updateDepthDiagnostic?.();
    if (this.mode === 'live') {
      await this.controller.stop({ clearMemory: true });
      this.renderStatus({ phase: 'live', message: 'Live-only mode · no analysis buffer or persistent cache.' });
    } else if (this.app.depthMode === 'live' && this.source) {
      await this.configure();
    }
  }

  async setSource(source) {
    this.source = source;
    this.configureGeneration += 1;
    this.lastPairKey = '';
    this.cachedDiagnostic = null;
    this.app.updateDepthDiagnostic?.();
    this.#resetHybridScore();
    if (this.mode === 'hybrid') return this.configure();
    return null;
  }

  setFusionMode(mode) {
    this.fusion.setMode(mode);
    this.lastPairKey = '';
    this.cachedDiagnostic = null;
    this.app.updateDepthDiagnostic?.();
  }

  async clearSource() {
    this.configureGeneration += 1;
    this.source = null;
    this.lastPairKey = '';
    this.cachedDiagnostic = null;
    this.app.updateDepthDiagnostic?.();
    this.fusion.reset();
    this.#resetBundledScore();
    this.#resetHybridScore();
    await this.controller.stop({ clearMemory: true });
    this.renderStatus({ phase: 'idle', message: 'Hybrid cache starts when a live video is imported.' });
  }

  async suspend() {
    this.configureGeneration += 1;
    this.lastPairKey = '';
    this.fusion.reset();
    this.#resetBundledScore();
    this.#resetHybridScore();
    await this.controller.stop({ clearMemory: true });
  }

  scheduleRestart(delayMs = 120) {
    if (this.mode !== 'hybrid' || !this.source || this.app.depthMode !== 'live') return;
    this.configureGeneration += 1;
    if (this.restartTimer != null) window.clearTimeout(this.restartTimer);
    this.restartTimer = window.setTimeout(() => {
      this.restartTimer = null;
      this.configure().catch(error => this.renderStatus({ phase: 'error', message: `Hybrid depth could not restart: ${error.message}` }));
    }, delayMs);
  }

  async configure() {
    if (this.mode !== 'hybrid' || !this.source || this.app.depthMode !== 'live') return null;
    if (this.restartTimer != null) window.clearTimeout(this.restartTimer);
    this.restartTimer = null;
    const configureGeneration = ++this.configureGeneration;
    const video = this.app.video;
    const activeModel = this.app.liveDepth.getActiveModelProfile?.() || this.app.liveDepth.getRequestedModelProfile?.();
    const machine = this.app.machineProfile || {};
    const config = {
      src: this.source.src,
      sourceIdentity: this.source.identity,
      sourceGeneration: this.app.sourceGeneration,
      startTime: video.currentTime,
      duration: video.duration,
      width: video.videoWidth,
      height: video.videoHeight,
      cols: this.app.activeCols,
      rows: this.app.activeRows,
      fps: selectedCacheRate(this.app, this.source),
      modelKey: activeModel?.key,
      backend: this.app.liveDepth.backend,
      precision: this.app.liveDepth.precision,
      invert: this.app.liveDepth.invert,
      sourceTitle: this.source.title,
      sourceBlob: this.source.blob || null,
      mediaInfo: this.source.mediaInfo || null,
      generationEnvironment: {
        cacheSampling: document.getElementById('cacheSampleRate')?.value || 'live',
        machine: {
          profile: machine.id || null,
          cpu: machine.cpuModel || null,
          gpu: machine.gpuLabel || null,
          systemMemoryGb: machine.systemMemoryGb || null,
          logicalCores: machine.hardwareConcurrency || null,
          webgpu: Boolean(machine.webgpu)
        },
        tuning: this.app.qualityGovernor?.snapshot?.() || null,
        modelInput: {
          detail: this.app.liveDepth.inputDetail,
          width: this.app.liveDepth.captureWidth,
          height: this.app.liveDepth.captureHeight
        },
        fusion: this.fusion.mode
      }
    };
    const result = await this.controller.loadSource(config);
    if (configureGeneration !== this.configureGeneration) return null;
    this.lastPairKey = '';
    this.fusion.reset();
    this.#resetHybridScore();
    this.library.refresh().catch(() => {});
    return result;
  }

  async prepareForPlayback(time) {
    if (this.mode !== 'hybrid') return true;
    return this.controller.prepareForPlayback(time);
  }

  renderFrame(time) {
    if (this.mode !== 'hybrid') return false;
    this.controller.setPlaybackTime(time);
    const state = this.controller.framesAt(time);
    if (!state) return true;
    const result = this.fusion.render({
      first: state.first,
      second: state.second,
      blend: state.blend,
      width: this.app.activeCols,
      height: this.app.activeRows,
      rgba: this.app.latestVideoPixels,
      sceneCut: state.sceneCut,
      provisional: state.provisional,
      firstGuide: state.firstGuide,
      secondGuide: state.secondGuide,
      pairKey: state.key,
      firstFrameKey: `${state.firstIndex}:${state.firstOrigin}`,
      secondFrameKey: `${state.secondIndex}:${state.secondOrigin}`,
      evidenceAmount: state.origin === 'shared' ? 0.3 : 0.2,
      videoFrameVersion: this.app.videoFrameVersion
    });
    if (!result.reused && result.frame) this.app.scene.updateDepthBuffers(result.frame, result.frame, 1);
    if (result.frame) {
      const snapshot = this.controller.snapshot();
      this.cachedDiagnostic = {
        frame: result.frame,
        width: this.app.activeCols,
        height: this.app.activeRows,
        mediaTime: Number(time) || 0,
        firstIndex: state.firstIndex,
        secondIndex: state.secondIndex,
        blend: state.blend,
        origin: state.origin,
        provisional: state.provisional,
        detailRecovery: result.detailRecovery,
        nativeFrames: snapshot.nativeFrames,
        reusedFrames: snapshot.reusedFrames,
        totalFrames: snapshot.totalFrames
      };
    }
    const scoreKey = `${state.firstIndex}:${state.secondIndex}`;
    if (!state.quality && result.frame && result.guide && scoreKey !== this.lastHybridScoreKey) {
      const quality = scoreDepthConversion({
        frame: result.frame,
        width: this.app.activeCols,
        height: this.app.activeRows,
        guide: result.guide,
        previousFrame: this.lastHybridScoreFrame,
        previousGuide: this.lastHybridScoreGuide,
        sceneCut: state.sceneCut
      });
      this.controller.recordPlaybackQuality(quality);
      this.lastHybridScoreKey = scoreKey;
      this.lastHybridScoreFrame = result.frame;
      this.lastHybridScoreGuide = result.guide;
    }
    this.lastPairKey = state.key;
    return true;
  }

  renderBundledFrame(depthData, time) {
    const state = depthData.framesAt(time, { smooth: false });
    const result = this.fusion.render({
      first: depthData.frame(state.first),
      second: depthData.frame(state.second),
      blend: state.blend,
      width: depthData.cols,
      height: depthData.rows,
      rgba: this.app.latestVideoPixels,
      sceneCut: Boolean(state.sceneCut),
      pairKey: `bundled:${state.first}:${state.second}`,
      firstFrameKey: `bundled:${state.first}`,
      secondFrameKey: `bundled:${state.second}`,
      videoFrameVersion: this.app.videoFrameVersion
    });
    if (!result.reused && result.frame) this.app.scene.updateDepthBuffers(result.frame, result.frame, 1);
    if (result.frame) {
      this.cachedDiagnostic = {
        frame: result.frame,
        width: depthData.cols,
        height: depthData.rows,
        mediaTime: Number(time) || 0,
        firstIndex: state.first,
        secondIndex: state.second,
        blend: state.blend,
        origin: 'bundled',
        provisional: false,
        detailRecovery: result.detailRecovery,
        nativeFrames: depthData.frameCount,
        reusedFrames: 0,
        totalFrames: depthData.frameCount
      };
    }
    const scoreKey = `${state.first}:${state.second}`;
    if (result.frame && result.guide && scoreKey !== this.lastBundledScoreKey) {
      const quality = scoreDepthConversion({
        frame: result.frame,
        width: depthData.cols,
        height: depthData.rows,
        guide: result.guide,
        previousFrame: this.lastBundledScoreFrame,
        previousGuide: this.lastBundledScoreGuide,
        sceneCut: state.first === state.second && state.blend === 0
      });
      this.bundledScore.add(quality);
      this.lastBundledScoreKey = scoreKey;
      this.lastBundledScoreFrame = result.frame;
      this.lastBundledScoreGuide = result.guide;
      this.renderQuality(this.bundledScore.snapshot());
    }
  }

  async listSessions() {
    await this.controller.store.initialize();
    return this.controller.store.listSessions();
  }

  getCachedDiagnostic() {
    return this.cachedDiagnostic;
  }

  async deleteSourceCache(sourceIdentity) {
    const activeIdentity = this.controller.source?.sourceIdentity;
    if (activeIdentity === sourceIdentity) {
      this.configureGeneration += 1;
      await this.controller.stop({ clearMemory: true });
      this.source = null;
      this.mode = 'live';
      this.controller.setMode('live');
      const modeControl = document.getElementById('depthPlaybackMode');
      if (modeControl) modeControl.value = 'live';
      this.fusion.reset();
      this.cachedDiagnostic = null;
      this.renderStatus({ phase: 'live', message: 'Active cache removed · playback continues in Live only mode.' });
    }
    return this.controller.store.deleteSourceCache(sourceIdentity);
  }

  async clearAllCaches() {
    const wasActive = Boolean(this.controller.source);
    this.configureGeneration += 1;
    await this.controller.stop({ clearMemory: true });
    this.source = null;
    if (wasActive) {
      this.mode = 'live';
      this.controller.setMode('live');
      const modeControl = document.getElementById('depthPlaybackMode');
      if (modeControl) modeControl.value = 'live';
    }
    this.fusion.reset();
    this.cachedDiagnostic = null;
    const result = await this.controller.store.clearAll();
    this.renderStatus({ phase: 'idle', message: 'All browser-local voxel conversions were removed.' });
    return result;
  }

  runtimeContextForSession(sessionId) {
    const active = this.controller.source?.cacheId === sessionId;
    return {
      active,
      mediaTimeSeconds: active ? Number(this.app.video.currentTime.toFixed(3)) : null,
      paused: active ? this.app.video.paused : null,
      fusion: this.fusion.mode,
      tuning: active ? (this.app.qualityGovernor?.snapshot?.() || null) : null,
      depthEngine: active ? {
        backend: this.app.liveDepth.backend,
        precision: this.app.liveDepth.precision,
        inputDetail: this.app.liveDepth.inputDetail,
        captureSize: [this.app.liveDepth.captureWidth, this.app.liveDepth.captureHeight]
      } : null
    };
  }

  async saveSessionFeedback(sessionId, feedback) {
    const current = await this.controller.store.getSession(sessionId);
    if (!current) throw new Error('That cached analysis no longer exists.');
    const runtime = this.runtimeContextForSession(sessionId);
    const previous = normalizeConversionFeedback(current.feedback);
    const requested = normalizeConversionFeedback(feedback);
    const stored = normalizeConversionFeedback({
      ...feedback,
      playbackTimeSeconds: runtime.active
        ? runtime.mediaTimeSeconds
        : (Object.hasOwn(feedback || {}, 'playbackTimeSeconds') ? requested.playbackTimeSeconds : previous.playbackTimeSeconds),
      updatedAt: Date.now()
    });
    await this.controller.store.touchVariant(sessionId, { feedback: stored });
    return this.controller.store.getSession(sessionId);
  }

  async restoreBestProfileForSource(sourceIdentity, { preferredSessionId = null } = {}) {
    await this.controller.store.initialize();
    const selected = selectBestResumableProfile(
      await this.controller.store.listSessions(),
      sourceIdentity,
      { pipeline: DEPTH_CACHE_PIPELINE_VERSION, preferredSessionId }
    );
    if (!selected) return null;

    // Frame keys are authoritative after an interrupted tab; session counters
    // intentionally checkpoint less often to keep IndexedDB write noise low.
    const indices = await this.controller.store.frameIndices(selected.id);
    const restored = { ...selected, frameCount: indices.length };
    restoreCacheSampling(restored);
    if (typeof this.app.restoreCachedQualityProfile === 'function') {
      await this.app.restoreCachedQualityProfile(restored);
    } else {
      const state = restoredProfileState(restored);
      this.app.liveDepth.setTargetFps(state.activeFps);
      this.app.liveDepth.setInvert(state.invert);
      await this.app.liveDepth.setModelProfile(state.model, { load: false });
      this.app.currentGridCols = state.activeDetail;
      this.app.setGridResolution(state.activeDetail);
    }
    const total = Math.max(1, Number(restored.totalFrames) || 1);
    const complete = indices.length + (Number(restored.reusableFrames) || 0) >= total;
    await this.controller.store.touchVariant(selected.id, {
      frameCount: indices.length,
      analysisState: complete ? 'complete' : 'in-progress',
      resumedAt: Date.now(),
      resumeCount: (Number(selected.resumeCount) || 0) + 1
    });
    this.renderStatus({
      phase: complete ? 'ready' : 'working',
      message: complete
        ? `Restored the best cached depth profile · ${indices.length}/${total} native frames.`
        : `Resuming the best cached depth profile · ${indices.length}/${total} native frames saved.`
    });
    return restored;
  }

  async replaySession(sessionId) {
    const session = await this.controller.store.getSession(sessionId);
    if (!session) throw new Error('That cached analysis no longer exists.');
    const source = await this.controller.store.getSource(session.sourceIdentity || session.descriptor?.source);
    if (!source?.blob && !source?.url) throw new Error('The video source is unavailable; re-import it to reuse these depth maps.');
    const src = source.blob ? URL.createObjectURL(source.blob) : source.url;
    await this.app.loadLiveMedia(src, source.title || session.sourceTitle || 'Cached video', {
      objectUrl: Boolean(source.blob),
      sourceBlob: source.blob || null,
      mediaInfo: source.mediaInfo || session.mediaInfo || null,
      sourceIdentity: source.id,
      resumeSessionId: session.id
    });
  }

  async recalibrateSession(sessionId, onProgress = null) {
    const session = await this.controller.store.getSession(sessionId);
    if (!session) throw new Error('That cached analysis no longer exists.');
    const active = this.controller.source?.cacheId === sessionId;
    const wasPlaying = active && !this.app.video.paused;
    if (active) {
      this.app.video.pause();
      await this.controller.stop({ clearMemory: true });
    }
    const recalibrator = new DepthCacheRecalibrator(this.controller.store, { onProgress });
    try {
      return await recalibrator.run(session);
    } finally {
      if (active) {
        await this.configure();
        if (wasPlaying) this.app.video.play().catch(() => {});
      }
      await this.library.refresh();
    }
  }

  renderStatus(state) {
    const line = document.getElementById('depthCacheCapability');
    if (!line || !state) return;
    line.textContent = state.message || 'Hybrid depth cache active.';
    line.dataset.state = state.phase === 'error' || state.phase === 'quota'
      ? 'missing'
      : state.phase === 'working' || state.phase === 'buffering'
        ? 'working'
        : 'ready';
    this.renderQuality(state.quality);
    this.app.updateDepthDiagnostic?.();
  }

  renderQuality(quality) {
    const scoreLine = document.getElementById('conversionScoreValue');
    if (scoreLine) {
      scoreLine.textContent = quality?.score == null
        ? 'Waiting for analyzed frames...'
        : `${quality.score}/100 - ${quality.grade} - ${quality.count} samples`;
      scoreLine.dataset.state = quality?.score == null ? 'working' : quality.score >= 55 ? 'ready' : 'missing';
      const components = quality?.components || {};
      scoreLine.title = quality?.score == null
        ? 'No-reference estimate of temporal stability, depth/image edge agreement, relief, borders and precision.'
        : `Edges ${components.edgeAlignment ?? '-'} - temporal ${components.temporalStability ?? '-'} - relief ${components.usefulRelief ?? '-'} - borders ${components.borderIntegrity ?? '-'} - precision ${components.precision ?? '-'}`;
    }
  }

  #resetBundledScore() {
    this.bundledScore = new ConversionScoreAccumulator();
    this.lastBundledScoreKey = '';
    this.lastBundledScoreFrame = null;
    this.lastBundledScoreGuide = null;
  }

  #resetHybridScore() {
    this.lastHybridScoreKey = '';
    this.lastHybridScoreFrame = null;
    this.lastHybridScoreGuide = null;
  }
}
