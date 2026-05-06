/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */
import React, { useCallback, useRef } from 'react';

interface ResizableImageProps {
  id: string;
  src: string;
  alt: string;
  initialWidth: string | null;
  onResize: (id: string, newWidth: string) => void;
}

export const ResizableImage: React.FC<ResizableImageProps> = ({
  id,
  src,
  alt,
  initialWidth,
  onResize,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const container = containerRef.current;
      if (!container || !container.parentElement) return;

      const startX = e.clientX;
      const startWidth = container.offsetWidth;
      const parentWidth = container.parentElement.offsetWidth;

      const handleMouseMove = (moveEvent: MouseEvent) => {
        const deltaX = moveEvent.clientX - startX;
        const newWidthPx = Math.max(100, startWidth + deltaX);
        const newWidthPercent = Math.min(100, (newWidthPx / parentWidth) * 100);
        container.style.width = `${newWidthPercent}%`;
      };

      const handleMouseUp = () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);

        if (container) {
          const finalWidthPx = container.offsetWidth;
          const finalWidthPercent = (finalWidthPx / parentWidth) * 100;
          container.style.width = `${finalWidthPercent.toFixed(2)}%`;
          onResize(id, `${finalWidthPercent.toFixed(2)}%`);
        }
      };

      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    },
    [id, onResize],
  );

  return (
    <div
      ref={containerRef}
      className="illustration-container resizable"
      style={{ width: initialWidth || '100%' }}
    >
      <img src={src} alt={alt} referrerPolicy="no-referrer" />
      <div className="resize-handle" onMouseDown={handleMouseDown}></div>
    </div>
  );
};
