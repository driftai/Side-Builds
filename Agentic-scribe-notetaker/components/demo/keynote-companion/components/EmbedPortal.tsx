/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom';

export const EmbedPortal: React.FC<{
  id: string;
  children: React.ReactNode;
  content: string;
}> = ({ id, children, content }) => {
  const [target, setTarget] = useState<HTMLElement | null>(null);

  useEffect(() => {
    setTarget(null);

    const findTarget = () => {
      const el = document.getElementById(`scribe-embed-${id}`);
      if (el) {
        setTarget(el);
        return true;
      }
      return false;
    };

    if (!findTarget()) {
      const interval = setInterval(() => {
        if (findTarget()) {
          clearInterval(interval);
        }
      }, 50);
      return () => clearInterval(interval);
    }
  }, [id, content]);

  if (!target) return null;
  return ReactDOM.createPortal(children, target);
};
