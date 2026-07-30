/**
 * @fileoverview Output Node Controller Component
 * @description Handles coordination when the audio output node is recreated,
 * ensuring all dependent components are updated with the new node reference
 * @license SPDX-License-Identifier: Apache-2.0
 */

import { LitElement, html } from 'lit';
import { customElement, property } from 'lit/decorators.js';

interface MasterVolumeController {
  outputNode: GainNode;
  applyCurrentVolumeToNode(): void;
}

interface AudioBufferHandler {
  outputNode: GainNode;
}

interface FadeController {
  outputNode: GainNode;
}

interface HostElement {
  outputNode: GainNode;
  requestUpdate(): void;
}

@customElement('output-node-controller')
export class OutputNodeController extends LitElement {
  @property({ type: Object }) masterVolumeController!: MasterVolumeController;
  @property({ type: Object }) audioBufferHandler!: AudioBufferHandler;
  @property({ type: Object }) fadeController!: FadeController;
  @property({ type: Object }) hostElement!: HostElement;

  /**
   * Handles output node recreation by updating all dependent components
   * @param newOutputNode The newly created GainNode
   */
  handleOutputNodeRecreated(newOutputNode: GainNode): void {
    console.log('OutputNodeController: Handling output node recreation, updating all dependent components');
    
    // Update host element's output node reference
    this.hostElement.outputNode = newOutputNode;
    
    // Update MasterVolumeController with new output node
    if (this.masterVolumeController) {
      this.masterVolumeController.outputNode = newOutputNode;
    }
    
    // Update AudioBufferHandler with new output node  
    if (this.audioBufferHandler) {
      this.audioBufferHandler.outputNode = newOutputNode;
    }
    
    // Update FadeController with new output node
    if (this.fadeController) {
      this.fadeController.outputNode = newOutputNode;
    }
    
    // Tell MasterVolumeController to apply its current volume to the new node
    if (this.masterVolumeController) {
      this.masterVolumeController.applyCurrentVolumeToNode();
    }
    
    // Trigger re-render to update component bindings
    if (this.hostElement) {
      this.hostElement.requestUpdate();
    }
    
    console.log('OutputNodeController: All components updated with new output node');
  }

  /**
   * Gets the current dependencies status for debugging
   */
  getDependenciesStatus() {
    return {
      masterVolumeController: !!this.masterVolumeController,
      audioBufferHandler: !!this.audioBufferHandler,
      fadeController: !!this.fadeController,
      hostElement: !!this.hostElement
    };
  }

  override render() {
    // This component doesn't render visible content, it's a logic controller
    return html``;
  }
} 