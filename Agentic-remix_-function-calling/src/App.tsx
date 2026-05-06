import { useState, useRef, useEffect, useCallback } from 'react';
import { GoogleGenAI, Type, Content, FunctionCall } from '@google/genai';
import { Send, Lightbulb, Loader2, ChevronDown, StopCircle, Timer } from 'lucide-react';
import { cn } from './lib/utils';

const FREE_MODELS = [
  { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash' },
  { id: 'gemini-2.5-flash-lite', name: '2.5 Flash-Lite' },
  { id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash' },
  { id: 'gemini-2.0-flash-lite', name: '2.0 Flash-Lite' },
] as const;

const ai = new GoogleGenAI({
  apiKey: process.env.GEMINI_API_KEY,
});

// ─── SCENE PRESETS ──────────────────────────────────────────
const SCENES: Record<string, { brightness: number; colorTemperature: 'daylight' | 'cool' | 'warm' }> = {
  movie:    { brightness: 10,  colorTemperature: 'warm' },
  reading:  { brightness: 80,  colorTemperature: 'daylight' },
  sleep:    { brightness: 5,   colorTemperature: 'warm' },
  focus:    { brightness: 100, colorTemperature: 'cool' },
  romantic: { brightness: 20,  colorTemperature: 'warm' },
  party:    { brightness: 80,  colorTemperature: 'cool' },
  relax:    { brightness: 40,  colorTemperature: 'warm' },
  sunrise:  { brightness: 100, colorTemperature: 'daylight' },
  sunset:   { brightness: 20,  colorTemperature: 'warm' },
};

// ─── FUNCTION DECLARATIONS ──────────────────────────────────
const controlLightFn = {
  name: 'controlLight',
  description: 'Set the brightness and color temperature of a room light instantly. When making multiple sequential adjustments, use delaySeconds to control the pause between each step.',
  parameters: {
    type: Type.OBJECT,
    properties: {
      brightness: {
        type: Type.NUMBER,
        description: 'Light level from 0 to 100. Zero is off and 100 is full brightness.',
      },
      colorTemperature: {
        type: Type.STRING,
        description: 'Color temperature: `daylight`, `cool` or `warm`.',
      },
      delaySeconds: {
        type: Type.NUMBER,
        description: 'Seconds to wait BEFORE applying this adjustment. Default 2. "every 5 seconds" → 5, "slowly" → 10, "quickly" → 1.',
      },
    },
    required: ['brightness', 'colorTemperature'],
  },
};

const fadeBrightnessFn = {
  name: 'fadeBrightness',
  description: 'Smoothly fade the light brightness from current level to a target over a duration. Use this instead of controlLight when the user wants gradual transitions like "fade to 0% over 30 seconds" or "slowly dim to 20%".',
  parameters: {
    type: Type.OBJECT,
    properties: {
      targetBrightness: {
        type: Type.NUMBER,
        description: 'Target brightness level (0-100).',
      },
      durationSeconds: {
        type: Type.NUMBER,
        description: 'How long the transition should take in seconds.',
      },
      targetColorTemperature: {
        type: Type.STRING,
        description: 'Optional target color temperature to fade to: `daylight`, `cool` or `warm`. If not set, keeps current.',
      },
    },
    required: ['targetBrightness', 'durationSeconds'],
  },
};

const applySceneFn = {
  name: 'applyScene',
  description: 'Apply a named lighting scene/preset. Available scenes: movie (10% warm), reading (80% daylight), sleep (5% warm), focus (100% cool), romantic (20% warm), party (80% cool), relax (40% warm). Fades smoothly over 3 seconds.',
  parameters: {
    type: Type.OBJECT,
    properties: {
      sceneName: {
        type: Type.STRING,
        description: 'Name of the scene to apply.',
      },
      fadeDurationSeconds: {
        type: Type.NUMBER,
        description: 'Optional fade duration in seconds. Default is 3.',
      },
    },
    required: ['sceneName'],
  },
};

const sunriseSunsetFn = {
  name: 'simulateSunriseSunset',
  description: 'Simulate a sunrise (dim warm → bright daylight) or sunset (bright daylight → dim warm) over a specified duration.',
  parameters: {
    type: Type.OBJECT,
    properties: {
      type: {
        type: Type.STRING,
        description: '"sunrise" or "sunset".',
      },
      durationMinutes: {
        type: Type.NUMBER,
        description: 'How long the simulation takes in minutes. Default is 5.',
      },
    },
    required: ['type'],
  },
};

const breathingEffectFn = {
  name: 'breathingEffect',
  description: 'Start a breathing/pulsing light effect that oscillates brightness between a min and max value. The effect runs continuously until the user gives another command.',
  parameters: {
    type: Type.OBJECT,
    properties: {
      minBrightness: {
        type: Type.NUMBER,
        description: 'Minimum brightness in the cycle (0-100).',
      },
      maxBrightness: {
        type: Type.NUMBER,
        description: 'Maximum brightness in the cycle (0-100).',
      },
      cycleDurationSeconds: {
        type: Type.NUMBER,
        description: 'How long one full breath cycle takes (up + down) in seconds. Default is 4.',
      },
    },
    required: ['minBrightness', 'maxBrightness'],
  },
};

const scheduleDimmingFn = {
  name: 'scheduleDimming',
  description: 'Schedule a brightness/temperature change to happen after a delay. Use for "turn off lights in 30 minutes" or "dim to 20% in 5 minutes".',
  parameters: {
    type: Type.OBJECT,
    properties: {
      targetBrightness: {
        type: Type.NUMBER,
        description: 'Target brightness level (0-100).',
      },
      delayMinutes: {
        type: Type.NUMBER,
        description: 'Minutes to wait before applying the change.',
      },
      colorTemperature: {
        type: Type.STRING,
        description: 'Optional target color temperature.',
      },
      fade: {
        type: Type.BOOLEAN,
        description: 'If true, fade to the target over 10 seconds instead of jumping instantly. Default true.',
      },
    },
    required: ['targetBrightness', 'delayMinutes'],
  },
};

const ALL_FUNCTIONS = [controlLightFn, fadeBrightnessFn, applySceneFn, sunriseSunsetFn, breathingEffectFn, scheduleDimmingFn];

// ─── TYPES ──────────────────────────────────────────────────
type Message = {
  role: 'user' | 'model';
  text: string;
  isFunctionCall?: boolean;
};

type ActiveEffect = {
  name: string;
  cancel: () => void;
};

// ─── COMPONENT ──────────────────────────────────────────────
export default function App() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'model', text: 'Hello! I am your smart home assistant. I can control the lights — brightness, color temperature, fading, scenes, sunrise/sunset simulation, breathing effects, and scheduled changes. Try "movie mode", "fade to 0% over 30 seconds", or "simulate sunrise".' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState(() => {
    const saved = localStorage.getItem('selectedModel');
    return saved && FREE_MODELS.some(m => m.id === saved) ? saved : FREE_MODELS[0].id;
  });
  useEffect(() => { localStorage.setItem('selectedModel', selectedModel); }, [selectedModel]);
  
  // Light state
  const [brightness, setBrightness] = useState(100);
  const [colorTemperature, setColorTemperature] = useState<'daylight' | 'cool' | 'warm'>('daylight');

  // Effect management
  const [activeEffect, setActiveEffect] = useState<string | null>(null);
  const [effectProgress, setEffectProgress] = useState<{ elapsed: number; total: number | null } | null>(null);
  const progressIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const activeEffectRef = useRef<ActiveEffect | null>(null);
  const brightnessRef = useRef(brightness);
  const colorTempRef = useRef(colorTemperature);

  // Keep refs in sync
  useEffect(() => { brightnessRef.current = brightness; }, [brightness]);
  useEffect(() => { colorTempRef.current = colorTemperature; }, [colorTemperature]);

  // GenAI history
  const historyRef = useRef<Content[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ─── HARDWARE SYNC ──────────────────────────────────────
  // Don't sync to hardware until we've read the actual screen state
  const isHydrated = useRef(false);

  // On load, read the current screen brightness and sync the UI
  useEffect(() => {
    fetch('/api/brightness')
      .then(r => r.json())
      .then(data => {
        if (data.ok && data.brightness >= 0) {
          setBrightness(data.brightness);
        }
      })
      .catch(() => {})
      .finally(() => {
        // Allow hardware sync after initial read
        isHydrated.current = true;
      });
  }, []);

  // Sync brightness state → actual screen brightness (only after hydration)
  useEffect(() => {
    if (!isHydrated.current) return;
    fetch('/api/brightness', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brightness }),
    }).catch(err => console.warn('[Brightness sync] Failed:', err));
  }, [brightness]);

  // Sync color temperature → Night Light (only after hydration)
  useEffect(() => {
    if (!isHydrated.current) return;
    fetch('/api/color-temperature', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ temperature: colorTemperature }),
    }).catch(err => console.warn('[ColorTemp sync] Failed:', err));
  }, [colorTemperature]);

  // ─── EFFECT HELPERS ─────────────────────────────────────
  const cancelEffect = useCallback(() => {
    if (activeEffectRef.current) {
      activeEffectRef.current.cancel();
      activeEffectRef.current = null;
      setActiveEffect(null);
    }
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
    }
    setEffectProgress(null);
  }, []);

  // durationSec = null for infinite effects (breathing)
  const registerEffect = useCallback((name: string, cancel: () => void, durationSec: number | null = null) => {
    cancelEffect();
    activeEffectRef.current = { name, cancel };
    setActiveEffect(name);

    // Start progress timer
    const startTime = Date.now();
    setEffectProgress({ elapsed: 0, total: durationSec });
    progressIntervalRef.current = setInterval(() => {
      const elapsed = Math.round((Date.now() - startTime) / 1000);
      setEffectProgress({ elapsed, total: durationSec });

      // Auto-clear progress when finite effect completes
      if (durationSec !== null && elapsed >= durationSec) {
        if (progressIntervalRef.current) {
          clearInterval(progressIntervalRef.current);
          progressIntervalRef.current = null;
        }
        setEffectProgress(null);
      }
    }, 1000);
  }, [cancelEffect]);

  // Smooth fade implementation
  const startFade = useCallback((
    targetBrightness: number,
    durationSeconds: number,
    targetTemp?: 'daylight' | 'cool' | 'warm'
  ) => {
    const startBright = brightnessRef.current;
    const steps = Math.max(1, Math.round(durationSeconds * 4)); // 4 updates/sec
    const stepMs = (durationSeconds * 1000) / steps;
    const brightStep = (targetBrightness - startBright) / steps;
    let currentStep = 0;

    // Set color temp immediately if changing
    if (targetTemp && targetTemp !== colorTempRef.current) {
      setColorTemperature(targetTemp);
    }

    const interval = setInterval(() => {
      currentStep++;
      if (currentStep >= steps) {
        setBrightness(targetBrightness);
        clearInterval(interval);
        if (activeEffectRef.current?.name.startsWith('Fading')) {
          activeEffectRef.current = null;
          setActiveEffect(null);
        }
      } else {
        setBrightness(Math.round(startBright + brightStep * currentStep));
      }
    }, stepMs);

    registerEffect(`Fading to ${targetBrightness}%`, () => clearInterval(interval), durationSeconds);
  }, [registerEffect]);

  // Breathing effect implementation
  const startBreathing = useCallback((
    minBright: number,
    maxBright: number,
    cycleSec: number
  ) => {
    const stepsPerCycle = Math.round(cycleSec * 4);
    let step = 0;

    const interval = setInterval(() => {
      // Sine wave oscillation: 0→1→0→-1→0 mapped to minBright↔maxBright
      const t = (step % stepsPerCycle) / stepsPerCycle;
      const sineVal = (Math.sin(t * 2 * Math.PI - Math.PI / 2) + 1) / 2; // 0 to 1
      const bright = Math.round(minBright + (maxBright - minBright) * sineVal);
      setBrightness(bright);
      step++;
    }, (cycleSec * 1000) / stepsPerCycle);

    registerEffect(`Breathing ${minBright}%-${maxBright}%`, () => clearInterval(interval), null); // infinite
  }, [registerEffect]);

  // Sunrise/sunset implementation
  const startSunriseSunset = useCallback((
    type: 'sunrise' | 'sunset',
    durationMin: number
  ) => {
    const durationMs = durationMin * 60 * 1000;
    const steps = Math.round(durationMin * 60 * 2); // 2 updates/sec
    const stepMs = durationMs / steps;
    let currentStep = 0;

    // Sunrise: warm 5% → daylight 100%
    // Sunset:  daylight 100% → warm 5%
    const startBright = type === 'sunrise' ? 5 : 100;
    const endBright = type === 'sunrise' ? 100 : 5;
    const brightStep = (endBright - startBright) / steps;

    // Change color temp at midpoint
    const midStep = Math.floor(steps / 2);
    if (type === 'sunrise') {
      setColorTemperature('warm');
      setBrightness(5);
    } else {
      setColorTemperature('daylight');
      setBrightness(100);
    }

    const interval = setInterval(() => {
      currentStep++;

      // Temp transition at midpoint
      if (currentStep === midStep) {
        setColorTemperature(type === 'sunrise' ? 'daylight' : 'warm');
      }

      if (currentStep >= steps) {
        setBrightness(endBright);
        clearInterval(interval);
        activeEffectRef.current = null;
        setActiveEffect(null);
      } else {
        setBrightness(Math.round(startBright + brightStep * currentStep));
      }
    }, stepMs);

    registerEffect(
      type === 'sunrise' ? `Sunrise (${durationMin}min)` : `Sunset (${durationMin}min)`,
      () => clearInterval(interval),
      durationMin * 60
    );
  }, [registerEffect]);

  // ─── FUNCTION CALL HANDLER ──────────────────────────────
  const executeFunctionCall = useCallback((call: FunctionCall): string => {
    const args = call.args as any;

    switch (call.name) {
      case 'controlLight': {
        cancelEffect();
        if (args.brightness !== undefined) {
          setBrightness(Math.max(0, Math.min(100, args.brightness)));
        }
        if (args.colorTemperature) {
          const temp = args.colorTemperature.toLowerCase();
          if (['daylight', 'cool', 'warm'].includes(temp)) {
            setColorTemperature(temp as any);
          }
        }
        return `Set light to ${args.brightness}% brightness, ${args.colorTemperature} color.`;
      }

      case 'fadeBrightness': {
        const target = Math.max(0, Math.min(100, args.targetBrightness));
        const dur = args.durationSeconds || 5;
        const temp = args.targetColorTemperature?.toLowerCase();
        const validTemp = ['daylight', 'cool', 'warm'].includes(temp) ? temp : undefined;
        startFade(target, dur, validTemp);
        return `Fading to ${target}% over ${dur}s${validTemp ? ` (→ ${validTemp})` : ''}.`;
      }

      case 'applyScene': {
        const sceneName = args.sceneName?.toLowerCase();
        const scene = SCENES[sceneName];
        if (!scene) {
          return `Unknown scene "${sceneName}". Available: ${Object.keys(SCENES).join(', ')}.`;
        }
        const dur = args.fadeDurationSeconds || 3;
        startFade(scene.brightness, dur, scene.colorTemperature);
        return `Applying "${sceneName}" scene (${scene.brightness}% ${scene.colorTemperature}, ${dur}s fade).`;
      }

      case 'simulateSunriseSunset': {
        const simType = args.type?.toLowerCase() as 'sunrise' | 'sunset';
        if (simType !== 'sunrise' && simType !== 'sunset') {
          return `Invalid type "${args.type}". Use "sunrise" or "sunset".`;
        }
        const durMin = args.durationMinutes || 5;
        startSunriseSunset(simType, durMin);
        return `Simulating ${simType} over ${durMin} minutes.`;
      }

      case 'breathingEffect': {
        const minB = Math.max(0, Math.min(100, args.minBrightness));
        const maxB = Math.max(0, Math.min(100, args.maxBrightness));
        const cycle = args.cycleDurationSeconds || 4;
        startBreathing(minB, maxB, cycle);
        return `Breathing effect: ${minB}%↔${maxB}%, ${cycle}s per cycle. Say "stop" to end.`;
      }

      case 'scheduleDimming': {
        cancelEffect();
        const target = Math.max(0, Math.min(100, args.targetBrightness));
        const delayMin = args.delayMinutes;
        const shouldFade = args.fade !== false;
        const temp = args.colorTemperature?.toLowerCase();

        const timeout = setTimeout(() => {
          if (shouldFade) {
            startFade(target, 10, ['daylight', 'cool', 'warm'].includes(temp) ? temp : undefined);
          } else {
            setBrightness(target);
            if (['daylight', 'cool', 'warm'].includes(temp)) {
              setColorTemperature(temp as any);
            }
          }
          activeEffectRef.current = null;
          setActiveEffect(null);
        }, delayMin * 60 * 1000);

        registerEffect(`Scheduled: ${target}% in ${delayMin}min`, () => clearTimeout(timeout), delayMin * 60);
        return `Scheduled: light will ${shouldFade ? 'fade' : 'set'} to ${target}%${temp ? ` (${temp})` : ''} in ${delayMin} minutes.`;
      }

      default:
        return `Unknown function: ${call.name}`;
    }
  }, [cancelEffect, startFade, startBreathing, startSunriseSunset, registerEffect]);

  // ─── SEND MESSAGE ───────────────────────────────────────
  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userText = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: userText }]);
    setIsLoading(true);

    // "stop" command cancels active effects
    if (/^(stop|cancel|halt)$/i.test(userText)) {
      cancelEffect();
      setMessages(prev => [...prev, { role: 'model', text: 'Effect stopped.' }]);
      setIsLoading(false);
      return;
    }

    try {
      historyRef.current.push({ role: 'user', parts: [{ text: userText }] });

      const response = await ai.models.generateContent({
        model: selectedModel,
        contents: historyRef.current,
        config: {
          systemInstruction: `You are a smart home light controller. Current state: brightness=${brightnessRef.current}%, colorTemperature=${colorTempRef.current}, activeEffect=${activeEffect || 'none'}.

Rules:
- When the user doesn't specify color temperature, keep the current one.
- Execute actions immediately without asking for clarification.
- For multi-step instant changes, return multiple controlLight calls in one response.
- For gradual transitions, use fadeBrightness.
- For presets like "movie mode" or "reading mode", use applyScene.
- For sunrise/sunset, use simulateSunriseSunset.
- For pulsing/breathing, use breathingEffect.
- For delayed changes like "turn off in 30 min", use scheduleDimming.
- Only call the functions the user is asking for right now. Don't repeat previous requests.`,
          tools: [{ functionDeclarations: ALL_FUNCTIONS }],
        }
      });

      const functionCalls = response.functionCalls;
      
      if (functionCalls && functionCalls.length > 0) {
        for (let i = 0; i < functionCalls.length; i++) {
          const call = functionCalls[i];

          // Delay between sequential controlLight calls
          if (call.name === 'controlLight' && i > 0) {
            const args = call.args as any;
            const delayMs = (args.delaySeconds ?? 2) * 1000;
            await new Promise(resolve => setTimeout(resolve, delayMs));
          }

          const result = executeFunctionCall(call);
          setMessages(prev => [...prev, { 
            role: 'model', 
            text: `[${call.name}: ${result}]`,
            isFunctionCall: true
          }]);
        }

        // Push summary to history (no continuation prompt)
        const summaryText = functionCalls.map(c => `${c.name}(${JSON.stringify(c.args)})`).join('; ');
        historyRef.current.push({
          role: 'model',
          parts: [{ text: `Done: ${summaryText}` }]
        });
      } else {
        const text = response.text;
        if (text) {
          historyRef.current.push({ role: 'model', parts: [{ text }] });
          setMessages(prev => [...prev, { role: 'model', text }]);
        }
      }
    } catch (error: any) {
      console.error('Error generating content:', error);
      let errorMessage: string;
      if (error?.status === 429 || error?.message?.includes('429') || error?.message?.includes('RESOURCE_EXHAUSTED')) {
        errorMessage = `Rate limit hit on ${FREE_MODELS.find(m => m.id === selectedModel)?.name}. Wait ~60s or switch models.`;
      } else {
        const detail = error?.message || error?.statusText || String(error);
        errorMessage = `Error (${selectedModel}): ${detail.slice(0, 200)}`;
      }
      setMessages(prev => [...prev, { role: 'model', text: errorMessage }]);
    } finally {
      setIsLoading(false);
    }
  };

  // ─── VISUAL HELPERS ─────────────────────────────────────
  const getLightColor = () => {
    if (brightness === 0) return 'rgba(255, 255, 255, 0.1)';
    const alpha = Math.max(0.2, brightness / 100);
    switch (colorTemperature) {
      case 'warm': return `rgba(255, 170, 50, ${alpha})`;
      case 'cool': return `rgba(200, 230, 255, ${alpha})`;
      case 'daylight': return `rgba(255, 240, 220, ${alpha})`;
      default: return `rgba(255, 255, 255, ${alpha})`;
    }
  };

  const getGlowColor = () => {
    if (brightness === 0) return 'transparent';
    const alpha = (brightness / 100) * 0.6;
    switch (colorTemperature) {
      case 'warm': return `rgba(255, 170, 50, ${alpha})`;
      case 'cool': return `rgba(200, 230, 255, ${alpha})`;
      case 'daylight': return `rgba(255, 240, 220, ${alpha})`;
      default: return `rgba(255, 255, 255, ${alpha})`;
    }
  };

  // ─── RENDER ─────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 flex flex-col md:flex-row font-sans">
      {/* Left panel: Smart Home Visualization */}
      <div className="flex-1 p-8 flex flex-col items-center justify-center border-b md:border-b-0 md:border-r border-slate-800 relative overflow-hidden">
        {/* Background glow */}
        <div 
          className="absolute inset-0 transition-colors duration-500 ease-in-out pointer-events-none"
          style={{ 
            background: `radial-gradient(circle at center, ${getGlowColor()} 0%, transparent 70%)` 
          }}
        />
        
        <div className="z-10 flex flex-col items-center gap-8">
          <div className="relative">
            <Lightbulb 
              size={120} 
              className="transition-colors duration-500 ease-in-out"
              style={{ 
                color: getLightColor(),
                filter: brightness > 0 ? `drop-shadow(0 0 ${brightness / 2}px ${getLightColor()})` : 'none'
              }} 
            />
          </div>
          
          <div className="bg-slate-900/80 backdrop-blur-md p-6 rounded-2xl border border-slate-800 shadow-xl w-64">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4 text-center">Room Status</h2>
            
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-400">Brightness</span>
                  <span className="font-mono">{brightness}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={brightness}
                  onChange={(e) => { cancelEffect(); setBrightness(Number(e.target.value)); }}
                  className="w-full h-2 bg-slate-800 rounded-full appearance-none cursor-pointer accent-blue-500"
                />
              </div>
              
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-slate-400">Temperature</span>
                </div>
                <div className="flex gap-2">
                  {(['warm', 'daylight', 'cool'] as const).map(temp => (
                    <button
                      key={temp}
                      onClick={() => { cancelEffect(); setColorTemperature(temp); }}
                      className={cn(
                        "flex-1 py-1.5 text-xs font-medium rounded-lg border transition-all capitalize",
                        colorTemperature === temp
                          ? temp === 'warm' ? 'bg-orange-500/20 border-orange-500/50 text-orange-300'
                          : temp === 'daylight' ? 'bg-yellow-400/20 border-yellow-400/50 text-yellow-200'
                          : 'bg-blue-400/20 border-blue-400/50 text-blue-300'
                          : 'bg-slate-800/50 border-slate-700/50 text-slate-500 hover:text-slate-300'
                      )}
                    >
                      {temp}
                    </button>
                  ))}
                </div>
              </div>

              {/* Active effect indicator with live timer */}
              {activeEffect && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                      <span className="text-xs text-green-400 font-mono">{activeEffect}</span>
                    </div>
                    <button
                      onClick={cancelEffect}
                      className="text-slate-500 hover:text-red-400 transition-colors"
                      title="Stop effect"
                    >
                      <StopCircle size={16} />
                    </button>
                  </div>
                  {effectProgress && (
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-xs font-mono">
                        <div className="flex items-center gap-1 text-slate-400">
                          <Timer size={10} />
                          <span>
                            {Math.floor(effectProgress.elapsed / 60)}:{String(effectProgress.elapsed % 60).padStart(2, '0')}
                          </span>
                        </div>
                        <span className="text-slate-500">
                          {effectProgress.total !== null
                            ? `${Math.floor(effectProgress.total / 60)}:${String(effectProgress.total % 60).padStart(2, '0')}` 
                            : '∞'}
                        </span>
                      </div>
                      {effectProgress.total !== null && (
                        <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-green-500/60 transition-all duration-1000 ease-linear"
                            style={{ width: `${Math.min(100, (effectProgress.elapsed / effectProgress.total) * 100)}%` }}
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Right panel: Chat Interface */}
      <div className="flex-1 flex flex-col h-[50vh] md:h-screen bg-slate-900 min-h-0">
        <div className="p-4 border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm shrink-0 flex items-center justify-between">
          <div>
            <h1 className="font-semibold text-lg">Assistant</h1>
            <p className="text-xs text-slate-400">Powered by {FREE_MODELS.find(m => m.id === selectedModel)?.name}</p>
          </div>
          <div className="relative">
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="appearance-none bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded-lg pl-3 pr-8 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
            >
              {FREE_MODELS.map(m => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
            <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          </div>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0 custom-scrollbar">
          {messages.map((msg, i) => (
            <div 
              key={i} 
              className={cn(
                "max-w-[85%] rounded-2xl p-4",
                msg.role === 'user' 
                  ? "bg-blue-600 text-white ml-auto rounded-br-sm" 
                  : msg.isFunctionCall
                    ? "bg-slate-800/50 text-slate-400 font-mono text-xs border border-slate-700/50 mr-auto"
                    : "bg-slate-800 text-slate-200 mr-auto rounded-bl-sm"
              )}
            >
              {msg.text}
            </div>
          ))}
          {isLoading && (
            <div className="bg-slate-800 text-slate-200 mr-auto rounded-2xl rounded-bl-sm p-4 max-w-[85%] flex items-center gap-2">
              <Loader2 size={16} className="animate-spin text-slate-400" />
              <span className="text-sm text-slate-400">Thinking...</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="p-4 bg-slate-900 border-t border-slate-800">
          <div className="flex gap-2 mb-3 overflow-x-auto pb-2 scrollbar-hide">
            {[
              "Movie mode",
              "Simulate sunrise",
              "Fade to 0% over 30s",
              "Breathe 20%-80%",
              "Turn off in 5 min",
            ].map(preset => (
              <button
                key={preset}
                onClick={() => setInput(preset)}
                className="whitespace-nowrap px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm rounded-full transition-colors border border-slate-700"
              >
                {preset}
              </button>
            ))}
          </div>
          <form 
            onSubmit={(e) => { e.preventDefault(); handleSend(); }}
            className="flex gap-2"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask to change the lights..."
              className="flex-1 bg-slate-800 border border-slate-700 rounded-full px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-shadow"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-500 text-white rounded-full p-3 transition-colors flex items-center justify-center"
            >
              <Send size={20} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
