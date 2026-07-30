import { css, html, LitElement, svg, CSSResultGroup } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { CircularButton } from '../CircularButton-Component/CircularButton.js';

type PlaybackState = 'stopped' | 'playing' | 'loading' | 'paused';

/** A button for toggling play/pause. */
@customElement('play-pause-button')
export class PlayPauseButton extends CircularButton {
  static override styles = css`
    .loader {
      stroke: #ffffff;
      stroke-width: 3;
      stroke-linecap: round;
      animation: spin linear 1s infinite;
      transform-origin: center;
      transform-box: fill-box;
    }
    @keyframes spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(359deg); }
    }
  ` as CSSResultGroup;

  @property({ type: String }) playbackState: PlaybackState = 'stopped';

  private renderPause() {
    return svg`<path
      d="M75.0037 69V39H83.7537V69H75.0037ZM56.2537 69V39H65.0037V69H56.2537Z"
      fill="#FEFEFE"
    />`;
  }

  private renderPlay() {
    return svg`<path d="M60 71.5V36.5L87.5 54L60 71.5Z" fill="#FEFEFE" />`;
  }

  private renderLoading() {
    return svg`<path shape-rendering="crispEdges" class="loader" d="M70,74.2L70,74.2c-10.7,0-19.5-8.7-19.5-19.5l0,0c0-10.7,8.7-19.5,19.5-19.5
            l0,0c10.7,0,19.5,8.7,19.5,19.5l0,0"/>`;
  }

  protected override renderIcon() {
    if (this.playbackState === 'playing') {
      return this.renderPause();
    } else if (this.playbackState === 'loading') {
      return this.renderLoading();
    } else {
      return this.renderPlay();
    }
  }
} 