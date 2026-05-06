/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
*/
import Modal from './Modal';
import { useAgent, useSourceStore, useUI, useUser } from '../lib/state';
import { Theme, themes } from '../lib/themes';
import { FONT_OPTIONS, PLACEHOLDER_DOC, IMAGE_MODEL_OPTIONS, LIVE_MODEL_PRESETS } from '../lib/constants';
import React, { useState, useRef } from 'react';
import * as pdfjs from 'pdfjs-dist';
import { FileUp, X, FileText, Loader2, ChevronDown, Key, Eye, EyeOff } from 'lucide-react';

// Set up PDF.js worker
// Using unpkg as it's often more reliable for specific versioned assets
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

type FormatOption = 'Markdown' | 'HTML';
const FORMAT_OPTIONS: FormatOption[] = ['Markdown', 'HTML'];

/**
 * A custom dropdown component for settings.
 */
function CustomDropdown({ 
  value, 
  options, 
  onChange, 
  placeholder 
}: { 
  value: string, 
  options: string[], 
  onChange: (val: string) => void,
  placeholder?: string
}) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="custom-dropdown-container" ref={containerRef}>
      <button 
        type="button"
        className="custom-dropdown-trigger"
        onClick={() => setIsOpen(!isOpen)}
      >
        <span>{value || placeholder}</span>
        <ChevronDown size={16} style={{ 
          transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
          transition: 'transform 0.2s',
          opacity: 0.5
        }} />
      </button>
      {isOpen && (
        <div className="custom-dropdown-menu">
          {options.map(option => (
            <button
              key={option}
              type="button"
              className={`custom-dropdown-item ${value === option ? 'active' : ''}`}
              onClick={() => {
                onChange(option);
                setIsOpen(false);
              }}
            >
              {option}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * A modal for configuring user settings for the writing session.
 * It features a modern, "jazzy" design for a more engaging user experience.
 */
export default function UserSettings() {
  // Hooks to manage user-specific data (name, info, topic, etc.)
  const { name, info, topic, format, setName, setInfo, setTopic, setFormat, pdfFiles, addPdfFile, removePdfFile } =
    useUser();
  const { upsertSource, deleteSource } = useSourceStore();
  // Hooks to manage UI state (modal visibility, current theme)
  const {
    setShowUserConfig, font, setFont, liveApiModel, setLiveApiModel,
    documentContent, apiKey, setApiKey, imageModel, setImageModel,
    imageGenerationEnabled, setImageGenerationEnabled,
  } = useUI();
  // Hooks to manage agent state (needed for updating agent color on theme change)
  const { current: agent, update: updateAgent } = useAgent();

  const [isUploading, setIsUploading] = useState(false);
  const [showApiKeyEdit, setShowApiKeyEdit] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [showCustomImageModel, setShowCustomImageModel] = useState(!IMAGE_MODEL_OPTIONS.includes(imageModel));

  const liveModelPreset = LIVE_MODEL_PRESETS.find(p => p.id === liveApiModel);
  const [showCustomLiveModel, setShowCustomLiveModel] = useState(!liveModelPreset);
  const fileInputRef = useRef<HTMLInputElement>(null);

  /**
   * A placeholder function that currently just closes the modal.
   */
  function updateClient() {
    setShowUserConfig(false);
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setIsUploading(true);
    try {
      for (const file of Array.from(files) as File[]) {
        if (file.type !== 'application/pdf') continue;

        const arrayBuffer = await file.arrayBuffer();
        const loadingTask = pdfjs.getDocument({ data: arrayBuffer });
        const pdf = await loadingTask.promise;
        
        let fullText = '';
        for (let i = 1; i <= pdf.numPages; i++) {
          const page = await pdf.getPage(i);
          const textContent = await page.getTextContent();
          const pageText = textContent.items
            .map((item: any) => item.str)
            .join(' ');
          fullText += pageText + '\n';
        }

        const pdfSource = {
          name: file.name,
          text: fullText,
        };
        addPdfFile(pdfSource);
        upsertSource(`pdf_${file.name}`, {
          kind: 'pdf',
          title: file.name,
          content: fullText,
          tags: ['cold', 'pdf'],
          active: true,
        });
      }
    } catch (error) {
      console.error('Error parsing PDF:', error);
      alert('Failed to parse PDF. Please try again.');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <Modal onClose={() => setShowUserConfig(false)}>
      <div className="userSettings jazzy">
        <h2>Configuration</h2>
        <p className="config-description">Tell us about yourself and what you'd like to write today.</p>

        <form
          onSubmit={e => {
            e.preventDefault();
            setShowUserConfig(false);
            updateClient();
          }}
        >
          <div className="settings-grid">
            <div>
              <p>Your name</p>
              <input
                type="text"
                name="name"
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="What do you like to be called?"
              />
            </div>

            <div>
              <p>Topic</p>
              <input
                type="text"
                name="topic"
                value={topic}
                onChange={e => setTopic(e.target.value)}
                placeholder="A journal entry, script for a play, recipe, poem, etc."
              />
            </div>
          </div>

          <div className="settings-grid">
            <div>
              <p>Document Font</p>
              <CustomDropdown
                value={font}
                options={FONT_OPTIONS}
                onChange={setFont}
                placeholder="Select a font"
              />
            </div>

            <div>
              <p>Live API Model</p>
              <CustomDropdown
                value={showCustomLiveModel ? 'Custom...' : (liveModelPreset?.label ?? 'Custom...')}
                options={[...LIVE_MODEL_PRESETS.map(p => p.label), 'Custom...']}
                onChange={(val) => {
                  if (val === 'Custom...') {
                    setShowCustomLiveModel(true);
                  } else {
                    const preset = LIVE_MODEL_PRESETS.find(p => p.label === val);
                    if (preset) {
                      setShowCustomLiveModel(false);
                      setLiveApiModel(preset.id);
                    }
                  }
                }}
              />
              {showCustomLiveModel && (
                <input
                  type="text"
                  value={liveApiModel}
                  onChange={(e) => setLiveApiModel(e.target.value)}
                  placeholder="Enter custom model ID"
                  style={{ marginTop: '8px' }}
                />
              )}
              <div className="active-model-caption" title="The model ID currently being sent to the Live API">
                Active: <span className="active-model-id">{liveApiModel || '(none set)'}</span>
              </div>
            </div>
          </div>

          <div className="settings-grid">
            <div>
              <p>Image Generation Model</p>
              <label style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={imageGenerationEnabled}
                  onChange={e => setImageGenerationEnabled(e.target.checked)}
                  style={{ width: '18px', height: '18px' }}
                />
                <span>Enable image generation</span>
              </label>
              <CustomDropdown
                value={showCustomImageModel ? 'Custom...' : imageModel}
                options={[...IMAGE_MODEL_OPTIONS, 'Custom...']}
                onChange={(val) => {
                  if (val === 'Custom...') {
                    setShowCustomImageModel(true);
                  } else {
                    setShowCustomImageModel(false);
                    setImageModel(val);
                  }
                }}
                placeholder="Select image model"
              />
              {showCustomImageModel && (
                <input
                  type="text"
                  value={imageModel}
                  onChange={(e) => setImageModel(e.target.value)}
                  placeholder="Enter custom model ID"
                  style={{ marginTop: '8px' }}
                />
              )}
            </div>
          </div>

          <details style={{ marginTop: '15px' }}>
            <summary>Context (Optional)</summary>
            <div className="details-content">
              <p className="context-description">
                Provide any background info worth knowing for this session.
              </p>
              <textarea
                rows={3}
                name="info"
                value={info}
                onChange={e => setInfo(e.target.value)}
                placeholder="e.g., names, facts, style preferences"
              />

              <div className="context-section" style={{ marginTop: '20px' }}>
                <p>PDF Context</p>
                <div className="pdf-upload-container">
                  <input
                    type="file"
                    accept=".pdf"
                    multiple
                    onChange={handleFileChange}
                    style={{ display: 'none' }}
                    ref={fileInputRef}
                  />
                  <button
                    type="button"
                    className="pdf-upload-button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploading}
                  >
                    {isUploading ? (
                      <Loader2 className="animate-spin" size={18} />
                    ) : (
                      <FileUp size={18} />
                    )}
                    <span>{isUploading ? 'Processing...' : 'Upload PDFs'}</span>
                  </button>

                  {pdfFiles.length > 0 && (
                    <div className="pdf-list">
                      {pdfFiles.map(file => (
                        <div key={file.name} className="pdf-item">
                          <FileText size={14} className="pdf-icon" />
                          <span className="pdf-name" title={file.name}>{file.name}</span>
                          <button
                            type="button"
                            className="pdf-remove"
                            onClick={() => {
                              removePdfFile(file.name);
                              deleteSource(`pdf_${file.name}`);
                            }}
                          >
                            <X size={14} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </details>

          {documentContent === PLACEHOLDER_DOC && (
            <div>
              <p>Output Format</p>
              <div className="format-selector">
                {FORMAT_OPTIONS.map(f => (
                  <label key={f} className="format-option">
                    <input
                      type="radio"
                      name="format"
                      value={f}
                      checked={format === f}
                      onChange={() => setFormat(f)}
                    />
                    <span>{f}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          <details style={{ marginTop: '15px' }}>
            <summary>API Key</summary>
            <div className="details-content">
              <p className="context-description">
                Your Gemini API key is stored locally in your browser.
              </p>
              {!showApiKeyEdit ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div className="api-key-display">
                    <Key size={14} style={{ opacity: 0.5, flexShrink: 0 }} />
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
                      {apiKey ? `${apiKey.slice(0, 6)}${'*'.repeat(20)}${apiKey.slice(-4)}` : 'Not set'}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="pdf-upload-button"
                    style={{ whiteSpace: 'nowrap', flexShrink: 0 }}
                    onClick={() => { setApiKeyInput(''); setShowApiKeyEdit(true); }}
                  >
                    <span>{apiKey ? 'Change' : 'Set Key'}</span>
                  </button>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div className="api-key-input-inline-wrapper">
                      <input
                        type={showApiKey ? 'text' : 'password'}
                        value={apiKeyInput}
                        onChange={e => setApiKeyInput(e.target.value)}
                        placeholder="Paste new API key..."
                        className="api-key-input-inline"
                        autoFocus
                        spellCheck={false}
                        autoComplete="off"
                      />
                      <button
                        type="button"
                        className="api-key-vis-toggle"
                        onClick={() => setShowApiKey(!showApiKey)}
                      >
                        {showApiKey ? <EyeOff size={14} /> : <Eye size={14} />}
                      </button>
                    </div>
                    <button
                      type="button"
                      className="pdf-upload-button"
                      style={{ whiteSpace: 'nowrap' }}
                      disabled={!apiKeyInput.trim()}
                      onClick={() => {
                        setApiKey(apiKeyInput.trim());
                        setShowApiKeyEdit(false);
                        setApiKeyInput('');
                      }}
                    >
                      <span>Save</span>
                    </button>
                    <button
                      type="button"
                      className="pdf-upload-button"
                      style={{ whiteSpace: 'nowrap' }}
                      onClick={() => setShowApiKeyEdit(false)}
                    >
                      <span>Cancel</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </details>

          <button className="button primary" style={{ marginTop: '20px' }}>Let's go!</button>
        </form>
      </div>
    </Modal>
  );
}
