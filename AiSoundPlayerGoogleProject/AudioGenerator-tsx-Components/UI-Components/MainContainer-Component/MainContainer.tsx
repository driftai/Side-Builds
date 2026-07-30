import { css, html, LitElement, CSSResultGroup } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { styleMap } from 'lit/directives/style-map.js';

interface BackgroundGenerator {
  prompts: Map<string, any>;
  generateBackground(): string;
}

@customElement('main-container')
export class MainContainer extends LitElement {
  static override styles = css`
    :host {
      height: 100vh;
      width: 100vw;
      min-height: 100vh;
      min-width: 100vw;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      box-sizing: border-box;
      position: fixed;
      top: 0;
      left: 0;
      overflow: hidden;
      margin: 0;
      padding: 0;
    }
    #background {
      will-change: background-image;
      position: absolute;
      top: 0;
      left: 0;
      height: 100vh;
      width: 100vw;
      min-height: 100vh;
      min-width: 100vw;
      z-index: -1;
      background: #111;
    }
  ` as CSSResultGroup;

  @property({ type: Object }) backgroundGenerator!: BackgroundGenerator;
  @property({ type: Object }) prompts!: Map<string, any>; // Added prompts as reactive property

  override render() {
    // Ensure background generator has the latest prompts before generating background
    if (this.backgroundGenerator && this.prompts) {
      this.backgroundGenerator.prompts = this.prompts;
    }
    
    const bg = styleMap({
      backgroundImage: this.backgroundGenerator?.generateBackground() || '',
    });

    return html`
      <div id="background" style=${bg}></div>
      <slot></slot>
    `;
  }
} 