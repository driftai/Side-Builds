/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import { create } from 'zustand';
import {
  Agent,
  Alice,
  Amelie,
  Ari,
  Defne,
  Hans,
  Hiro,
  Ines,
  Irene,
  Jiwon,
  Karim,
  Luca,
  Mei,
  Newton,
  Olga,
  Rahul,
  Ramon,
  Reza,
  Sam,
  Tom,
} from '../presets/agents';

function getAgentById(id: string) {
  const { availablePersonal, availablePresets } = useAgent.getState();
  return (
    availablePersonal.find(agent => agent.id === id) ||
    availablePresets.find(agent => agent.id === id)
  );
}

export const useAgent = create<{
  current: Agent;
  availablePresets: Agent[];
  availablePersonal: Agent[];
  setCurrent: (agent: Agent | string) => void;
  addAgent: (agent: Agent) => void;
  update: (agentId: string, adjustments: Partial<Agent>) => void;
}>(set => ({
  current: Alice,
  availablePresets: [
    Alice,
    Sam,
    Irene,
    Tom,
    Rahul,
    Ramon,
    Amelie,
    Ari,
    Mei,
    Hiro,
    Jiwon,
    Hans,
    Newton,
    Defne,
    Karim,
    Reza,
    Ines,
    Olga,
    Luca,
  ],
  availablePersonal: [],

  addAgent: (agent: Agent) => {
    set(state => ({
      availablePersonal: [...state.availablePersonal, agent],
      current: agent,
    }));
  },
  setCurrent: (agent: Agent | string) =>
    set({ current: typeof agent === 'string' ? getAgentById(agent) : agent }),
  update: (agentId: string, adjustments: Partial<Agent>) => {
    const agent = getAgentById(agentId);
    if (!agent) return;
    const updatedAgent = { ...agent, ...adjustments };
    set(state => ({
      availablePresets: state.availablePresets.map(a =>
        a.id === agentId ? updatedAgent : a
      ),
      availablePersonal: state.availablePersonal.map(a =>
        a.id === agentId ? updatedAgent : a
      ),
      current: state.current.id === agentId ? updatedAgent : state.current,
    }));
  },
}));
