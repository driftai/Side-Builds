import { LitElement } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { VisualizationMode } from '../TypeDefinitions-Component/TypeDefinitions.js';

interface ToastMessage {
  show(message: string): void;
}

@customElement('ui-state-controller')
export class UIStateController extends LitElement {
    @state() private _showSettingsPanel = false;
    @state() private _visualizationMode: VisualizationMode = 'frequency';

    @property({type: Object}) toastMessage?: ToastMessage;

    get showSettingsPanel() {
        return this._showSettingsPanel;
    }

    get visualizationMode() {
        return this._visualizationMode;
    }

    toggleSettingsPanel() {
        this._showSettingsPanel = !this._showSettingsPanel;
        this.dispatchStateChange();
    }

    setVisualizationMode(mode: VisualizationMode) {
        if (this._visualizationMode !== mode) {
            this._visualizationMode = mode;
            this.toastMessage?.show(`Visualization mode changed to: ${mode}`);
            this.dispatchStateChange();
        }
    }

    private dispatchStateChange() {
        const detail = {
            showSettingsPanel: this._showSettingsPanel,
            visualizationMode: this._visualizationMode,
        };
        this.dispatchEvent(new CustomEvent('ui-state-change', { detail, bubbles: true, composed: true }));
    }

    override render() {
        return null; // This is a controller component
    }
} 