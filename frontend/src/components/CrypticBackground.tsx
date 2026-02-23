import React, { useEffect, useRef } from 'react';

export const CrypticBackground: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = window.innerWidth;
    let height = window.innerHeight;
    canvas.width = width;
    canvas.height = height;

    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%^&*()_+~|}{[]:;?><,./-=' + 
                  'EPSTEINFILESCLASSIFIEDREDACTEDCONFIDENTIALEVIDENCE';
    
    const fontSize = 14;
    const columns = width / fontSize;
    const drops: number[] = [];

    for (let x = 0; x < columns; x++) {
      drops[x] = Math.random() * height;
    }

    const draw = () => {
      // Translucent black background to create trail effect
      ctx.fillStyle = 'rgba(9, 9, 11, 0.05)'; // zinc-950 with opacity
      ctx.fillRect(0, 0, width, height);

      ctx.fillStyle = 'rgba(63, 63, 70, 0.15)'; // zinc-700 with low opacity
      ctx.font = `${fontSize}px "JetBrains Mono", monospace`;

      for (let i = 0; i < drops.length; i++) {
        const text = chars[Math.floor(Math.random() * chars.length)];
        ctx.fillText(text, i * fontSize, drops[i] * fontSize);

        if (drops[i] * fontSize > height && Math.random() > 0.975) {
          drops[i] = 0;
        }
        drops[i]++;
      }
    };

    const interval = setInterval(draw, 50);

    const handleResize = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = width;
      canvas.height = height;
    };

    window.addEventListener('resize', handleResize);

    return () => {
      clearInterval(interval);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0 opacity-40"
      style={{ mixBlendMode: 'screen' }}
    />
  );
};
