import { LitElement } from 'lit';
import { customElement } from 'lit/decorators.js';

@customElement('viewport-controller')
export class ViewportController extends LitElement {
  
  /**
   * Applies document-level styles to make the app fill the screen
   * This should be called once during app initialization
   */
  static applyViewportStyles(): void {
    // Apply styles to make the app fill the screen
    document.documentElement.style.height = '100%';
    document.documentElement.style.margin = '0';
    document.documentElement.style.padding = '0';
    document.body.style.height = '100%';
    document.body.style.margin = '0';
    document.body.style.padding = '0';
  }

  /**
   * Resets document-level styles to browser defaults
   * This can be used for cleanup if needed
   */
  static resetViewportStyles(): void {
    document.documentElement.style.height = '';
    document.documentElement.style.margin = '';
    document.documentElement.style.padding = '';
    document.body.style.height = '';
    document.body.style.margin = '';
    document.body.style.padding = '';
  }

  /**
   * Applies flex display to the target element
   * Used to ensure components fill their containers properly
   */
  static applyFlexDisplay(element: HTMLElement): void {
    element.style.display = 'flex';
  }

  override render() {
    // This component doesn't render UI directly, it's a utility controller
    return null;
  }
} 