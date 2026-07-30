/**
 * @fileoverview Filtered Prompts Controller Component
 * @description Manages filtered prompts state and handles adding/removing filtered prompts
 * that are rejected by the AI system
 * @license SPDX-License-Identifier: Apache-2.0
 */

import { LitElement, html } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

interface ToastMessage {
  show(message: string): void;
}

@customElement('filtered-prompts-controller')
export class FilteredPromptsController extends LitElement {
  @property({ type: Object }) toastMessage!: ToastMessage;
  
  @state() private filteredPrompts = new Set<string>();
  
  /**
   * Adds a new filtered prompt to the set
   * @param promptText - The text of the prompt that was filtered
   * @param filteredReason - Optional reason why the prompt was filtered
   */
  addFilteredPrompt(promptText: string, filteredReason?: string): void {
    this.filteredPrompts = new Set([...this.filteredPrompts, promptText]);
    
    // Show toast message if a reason was provided
    if (filteredReason && this.toastMessage) {
      this.toastMessage.show(filteredReason);
    }
    
    // Dispatch event to notify parent component of the change
    this.dispatchEvent(new CustomEvent('filtered-prompts-changed', {
      detail: this.filteredPrompts,
      bubbles: true,
      composed: true
    }));
  }
  
  /**
   * Removes a filtered prompt from the set
   * @param promptText - The text of the prompt to remove from filtered list
   */
  removeFilteredPrompt(promptText: string): void {
    const newFilteredPrompts = new Set(this.filteredPrompts);
    newFilteredPrompts.delete(promptText);
    this.filteredPrompts = newFilteredPrompts;
    
    // Dispatch event to notify parent component of the change
    this.dispatchEvent(new CustomEvent('filtered-prompts-changed', {
      detail: this.filteredPrompts,
      bubbles: true,
      composed: true
    }));
  }
  
  /**
   * Clears all filtered prompts
   */
  clearFilteredPrompts(): void {
    this.filteredPrompts = new Set<string>();
    
    // Dispatch event to notify parent component of the change
    this.dispatchEvent(new CustomEvent('filtered-prompts-changed', {
      detail: this.filteredPrompts,
      bubbles: true,
      composed: true
    }));
  }
  
  /**
   * Checks if a prompt is filtered
   * @param promptText - The text of the prompt to check
   * @returns true if the prompt is filtered, false otherwise
   */
  isPromptFiltered(promptText: string): boolean {
    return this.filteredPrompts.has(promptText);
  }
  
  /**
   * Gets the current set of filtered prompts
   * @returns Set of filtered prompt texts
   */
  getFilteredPrompts(): Set<string> {
    return new Set(this.filteredPrompts);
  }
  
  /**
   * Gets the count of currently filtered prompts
   * @returns Number of filtered prompts
   */
  getFilteredPromptsCount(): number {
    return this.filteredPrompts.size;
  }
  
  /**
   * Handles filtered prompt from server message
   * This method should be called when receiving filteredPrompt from LiveMusicServerMessage
   * @param filteredPrompt - The filtered prompt object from server
   */
  handleServerFilteredPrompt(filteredPrompt: { text?: string; filteredReason?: string }): void {
    if (filteredPrompt.text) {
      this.addFilteredPrompt(filteredPrompt.text, filteredPrompt.filteredReason);
    }
  }
  
  override render() {
    // This component doesn't render visible content, it's a logic controller
    return html``;
  }
} 