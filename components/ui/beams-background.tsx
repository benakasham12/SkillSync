"use client";

import React, { useEffect, useRef } from "react";

function cn(...classes: (string | undefined | false | null)[]) {
  return classes.filter(Boolean).join(" ");
}

export interface BeamsBackgroundProps extends React.HTMLAttributes<HTMLDivElement> {
  className?: string;
  children?: React.ReactNode;
  intensity?: "subtle" | "medium" | "strong";
}

interface Beam {
  x: number;
  y: number;
  width: number;
  length: number;
  angle: number;
  speed: number;
  opacity: number;
  hue: number;
  pulse: number;
  pulseSpeed: number;
}

function createBeam(width: number, height: number, isDarkMode: boolean): Beam {
  const angle = -35 + Math.random() * 10;
  // Flowing blue and purple palette (hue ~215 to ~270)
  const hueBase = isDarkMode ? 215 : 220;
  const hueRange = isDarkMode ? 55 : 45;

  return {
    x: Math.random() * width * 1.5 - width * 0.25,
    y: Math.random() * height * 1.5 - height * 0.25,
    width: 30 + Math.random() * 60,
    length: height * 2.2,
    angle,
    speed: 0.6 + Math.random() * 1.1,
    opacity: 0.12 + Math.random() * 0.16,
    hue: hueBase + Math.random() * hueRange,
    pulse: Math.random() * Math.PI * 2,
    pulseSpeed: 0.02 + Math.random() * 0.03,
  };
}

export function BeamsBackground({
  className,
  children,
  intensity = "strong",
  ...props
}: BeamsBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const beamsRef = useRef<Beam[]>([]);
  const animationFrameRef = useRef<number>(0);
  const isDarkModeRef = useRef<boolean>(false);
  const MINIMUM_BEAMS = 22;

  const opacityMap = {
    subtle: 0.65,
    medium: 0.82,
    strong: 1.0,
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Check for prefers-reduced-motion
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    // Detect dark mode from either class or data-theme
    const updateDarkMode = () => {
      isDarkModeRef.current =
        document.documentElement.classList.contains("dark") ||
        document.documentElement.getAttribute("data-theme") === "dark";
    };

    const observer = new MutationObserver(updateDarkMode);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class", "data-theme"],
    });

    updateDarkMode();

    const updateCanvasSize = () => {
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = rect.width || canvas.parentElement?.clientWidth || window.innerWidth;
      const h = rect.height || canvas.parentElement?.clientHeight || window.innerHeight;

      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.scale(dpr, dpr);

      const totalBeams = Math.floor(MINIMUM_BEAMS * 1.3);
      beamsRef.current = Array.from({ length: totalBeams }, () =>
        createBeam(w, h, isDarkModeRef.current)
      );

      if (prefersReducedMotion) {
        // Draw single static frame if user prefers reduced motion
        renderFrame(w, h);
      }
    };

    function resetBeam(beam: Beam, index: number, totalBeams: number, w: number, h: number) {
      const column = index % 3;
      const spacing = w / 3;
      const hueBase = isDarkModeRef.current ? 215 : 220;
      const hueRange = isDarkModeRef.current ? 55 : 45;

      beam.y = h + 100;
      beam.x = column * spacing + spacing / 2 + (Math.random() - 0.5) * spacing * 0.6;
      beam.width = 40 + Math.random() * 80;
      beam.speed = 0.5 + Math.random() * 0.8;
      beam.hue = hueBase + (index * hueRange) / totalBeams;
      beam.opacity = 0.15 + Math.random() * 0.12;
      return beam;
    }

    function drawBeam(ctx: CanvasRenderingContext2D, beam: Beam) {
      ctx.save();
      ctx.translate(beam.x, beam.y);
      ctx.rotate((beam.angle * Math.PI) / 180);

      const pulsingOpacity =
        beam.opacity *
        (0.8 + Math.sin(beam.pulse) * 0.2) *
        opacityMap[intensity];

      const gradient = ctx.createLinearGradient(0, 0, 0, beam.length);
      const saturation = isDarkModeRef.current ? "85%" : "75%";
      const lightness = isDarkModeRef.current ? "62%" : "48%";

      gradient.addColorStop(0, `hsla(${beam.hue}, ${saturation}, ${lightness}, 0)`);
      gradient.addColorStop(0.1, `hsla(${beam.hue}, ${saturation}, ${lightness}, ${pulsingOpacity * 0.4})`);
      gradient.addColorStop(0.4, `hsla(${beam.hue}, ${saturation}, ${lightness}, ${pulsingOpacity})`);
      gradient.addColorStop(0.6, `hsla(${beam.hue}, ${saturation}, ${lightness}, ${pulsingOpacity})`);
      gradient.addColorStop(0.9, `hsla(${beam.hue}, ${saturation}, ${lightness}, ${pulsingOpacity * 0.4})`);
      gradient.addColorStop(1, `hsla(${beam.hue}, ${saturation}, ${lightness}, 0)`);

      ctx.fillStyle = gradient;
      ctx.fillRect(-beam.width / 2, 0, beam.width, beam.length);
      ctx.restore();
    }

    function renderFrame(w: number, h: number) {
      ctx.clearRect(0, 0, w, h);
      ctx.filter = "blur(30px)";
      beamsRef.current.forEach((beam) => {
        drawBeam(ctx, beam);
      });
    }

    function animate() {
      if (!canvas || !ctx) return;
      const rect = canvas.getBoundingClientRect();
      const w = rect.width || window.innerWidth;
      const h = rect.height || window.innerHeight;

      ctx.clearRect(0, 0, w, h);
      ctx.filter = "blur(30px)";

      const totalBeams = beamsRef.current.length;
      beamsRef.current.forEach((beam, index) => {
        beam.y -= beam.speed;
        beam.pulse += beam.pulseSpeed;

        if (beam.y + beam.length < -100) {
          resetBeam(beam, index, totalBeams, w, h);
        }

        drawBeam(ctx, beam);
      });

      animationFrameRef.current = requestAnimationFrame(animate);
    }

    updateCanvasSize();
    window.addEventListener("resize", updateCanvasSize);

    if (!prefersReducedMotion) {
      animate();
    }

    return () => {
      window.removeEventListener("resize", updateCanvasSize);
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      observer.disconnect();
    };
  }, [intensity]);

  return (
    <div
      className={cn(
        "relative w-full overflow-hidden bg-slate-50 dark:bg-[#090d16]",
        className
      )}
      {...props}
    >
      <canvas
        ref={canvasRef}
        className="absolute inset-0 pointer-events-none z-0"
        style={{ filter: "blur(20px)" }}
        aria-hidden="true"
      />

      <div
        className="absolute inset-0 bg-blue-900/[0.03] dark:bg-indigo-950/[0.08] pointer-events-none z-[1]"
        style={{ backdropFilter: "blur(40px)" }}
        aria-hidden="true"
      />

      <div className="relative z-10 w-full">{children}</div>
    </div>
  );
}
