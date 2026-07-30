import { LitElement } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { GoogleGenAI, type LiveMusicSession, type LiveMusicServerMessage } from '@google/genai';

@customElement('google-ai-config')
export class GoogleAIConfig extends LitElement {
  @property({ type: String }) private apiKey: string = process.env.GEMINI_API_KEY || '';
  @property({ type: String }) private apiVersion: string = 'v1alpha';
  @property({ type: String }) private model: string = 'lyria-realtime-exp';

  private _ai: GoogleGenAI | null = null;

  constructor() {
    super();
    this.initializeAI();
  }

  /**
   * Initialize the Google AI client with configuration
   */
  private initializeAI(): void {
    if (!this.apiKey) {
      console.warn('GoogleAIConfig: No API key provided');
      return;
    }


    this._ai = new GoogleGenAI({
      apiKey: this.apiKey,
      apiVersion: this.apiVersion
    });
  }

  /**
   * Get the configured Google AI client instance
   */
  get ai(): GoogleGenAI | null {
    return this._ai;
  }

  /**
   * Get the configured model name
   */
  get modelName(): string {
    return this.model;
  }

  /**
   * Get the current configuration
   */
  get config() {
    return {
      apiKey: this.apiKey,
      apiVersion: this.apiVersion,
      model: this.model,
      isInitialized: this._ai !== null
    };
  }

  /**
   * Update the API key and reinitialize the AI client
   */
  updateApiKey(newApiKey: string): void {
    this.apiKey = newApiKey;
    this.initializeAI();
  }

  /**
   * Update the model name
   */
  updateModel(newModel: string): void {
    this.model = newModel;
  }

  /**
   * Update the API version and reinitialize the AI client
   */
  updateApiVersion(newApiVersion: string): void {
    this.apiVersion = newApiVersion;
    this.initializeAI();
  }

  /**
   * Create a live music session using the configured AI client
   */
  async createLiveMusicSession(callbacks: {
    onmessage: (e: LiveMusicServerMessage) => void;
    onerror: (e: ErrorEvent) => void;
    onclose: () => void;
  }): Promise<LiveMusicSession | null> {
    if (!this._ai) {
      console.error('GoogleAIConfig: AI client not initialized');
      return null;
    }

    try {
      return await this._ai.live.music.connect({
        model: this.model,
        callbacks
      });
    } catch (error) {
      console.error('GoogleAIConfig: Failed to create live music session:', error);
      return null;
    }
  }

  override render() {
    // This component doesn't render UI directly, it's a configuration utility
    return null;
  }
} 