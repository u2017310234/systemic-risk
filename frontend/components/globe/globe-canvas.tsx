"use client";

import { useEffect, useRef } from "react";

import { clamp } from "@/lib/utils";

type GlobeMarker = {
  id: string;
  label: string;
  lat: number;
  lon: number;
  size: number;
  color: string;
  selected?: boolean;
};

type ProjectedMarker = {
  id: string;
  x: number;
  y: number;
  r: number;
  visible: boolean;
};

type GlobeCanvasProps = {
  markers: GlobeMarker[];
  selectedId?: string | null;
  onSelect: (id: string) => void;
};

const MERIDIANS = [-150, -120, -90, -60, -30, 0, 30, 60, 90, 120, 150];
const PARALLELS = [-60, -30, 0, 30, 60];

export function GlobeCanvas({ markers, selectedId, onSelect }: GlobeCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const frameRef = useRef<number | null>(null);
  const projectedRef = useRef<ProjectedMarker[]>([]);
  const draggingRef = useRef(false);
  const pointerMovedRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const rotationRef = useRef({ lon: -20, lat: -12 });

  useEffect(() => {
    const canvasElement = canvasRef.current;
    if (!canvasElement) {
      return;
    }

    const context = canvasElement.getContext("2d");
    if (!context) {
      return;
    }

    const canvas: HTMLCanvasElement = canvasElement;
    const ctx: CanvasRenderingContext2D = context;

    function resize() {
      const rect = canvas.getBoundingClientRect();
      const ratio = window.devicePixelRatio || 1;
      canvas.width = rect.width * ratio;
      canvas.height = rect.height * ratio;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    }

    function draw() {
      const rect = canvas.getBoundingClientRect();
      const width = rect.width;
      const height = rect.height;
      const cx = width / 2;
      const cy = height / 2;
      const radius = Math.min(width, height) * 0.34;
      const rotation = rotationRef.current;

      ctx.clearRect(0, 0, width, height);

      drawBackdrop(ctx, width, height, cx, cy, radius);
      drawSphere(ctx, cx, cy, radius);

      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.clip();

      drawGrid(ctx, cx, cy, radius, rotation);
      projectedRef.current = drawMarkers(ctx, cx, cy, radius, markers, rotation, selectedId);

      ctx.restore();
      drawAtmosphere(ctx, cx, cy, radius);

      if (!draggingRef.current) {
        rotationRef.current.lon = rotationRef.current.lon + 0.12;
      }

      frameRef.current = window.requestAnimationFrame(draw);
    }

    resize();
    draw();

    const resizeObserver = new ResizeObserver(() => resize());
    resizeObserver.observe(canvas);

    return () => {
      resizeObserver.disconnect();
      if (frameRef.current) {
        window.cancelAnimationFrame(frameRef.current);
      }
    };
  }, [markers, onSelect, selectedId]);

  function handlePointerDown(event: React.PointerEvent<HTMLCanvasElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    draggingRef.current = true;
    pointerMovedRef.current = false;
    dragStartRef.current = { x: event.clientX, y: event.clientY };
  }

  function handlePointerMove(event: React.PointerEvent<HTMLCanvasElement>) {
    if (!draggingRef.current) {
      return;
    }
    const deltaX = event.clientX - dragStartRef.current.x;
    const deltaY = event.clientY - dragStartRef.current.y;

    if (Math.abs(deltaX) > 2 || Math.abs(deltaY) > 2) {
      pointerMovedRef.current = true;
    }

    rotationRef.current = {
      lon: rotationRef.current.lon + deltaX * 0.28,
      lat: clamp(rotationRef.current.lat + deltaY * 0.18, -70, 70)
    };
    dragStartRef.current = { x: event.clientX, y: event.clientY };
  }

  function handlePointerUp(event: React.PointerEvent<HTMLCanvasElement>) {
    event.currentTarget.releasePointerCapture(event.pointerId);
    draggingRef.current = false;

    if (pointerMovedRef.current) {
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const hit = projectedRef.current.find(
      (marker) => marker.visible && Math.hypot(marker.x - x, marker.y - y) <= marker.r + 8
    );
    if (hit) {
      onSelect(hit.id);
    }
  }

  return (
    <canvas
      ref={canvasRef}
      className="h-[540px] w-full touch-none rounded-[30px] border border-line/60 bg-[#020811]"
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
    />
  );
}

function drawBackdrop(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  cx: number,
  cy: number,
  radius: number
) {
  const gradient = context.createRadialGradient(cx, cy, radius * 0.35, cx, cy, radius * 1.9);
  gradient.addColorStop(0, "rgba(17, 58, 95, 0.28)");
  gradient.addColorStop(0.6, "rgba(4, 12, 22, 0.42)");
  gradient.addColorStop(1, "rgba(2, 8, 17, 1)");
  context.fillStyle = gradient;
  context.fillRect(0, 0, width, height);

  context.save();
  for (let index = 0; index < 90; index += 1) {
    const x = ((index * 83) % width) + ((index % 3) * 11);
    const y = ((index * 137) % height) + ((index % 5) * 7);
    const opacity = 0.1 + ((index * 17) % 20) / 100;
    context.fillStyle = `rgba(220, 240, 255, ${opacity})`;
    context.fillRect(x % width, y % height, 1.5, 1.5);
  }
  context.restore();
}

function drawSphere(context: CanvasRenderingContext2D, cx: number, cy: number, radius: number) {
  const fill = context.createRadialGradient(cx - radius * 0.28, cy - radius * 0.35, radius * 0.15, cx, cy, radius);
  fill.addColorStop(0, "rgba(35, 120, 183, 0.88)");
  fill.addColorStop(0.45, "rgba(11, 43, 72, 0.96)");
  fill.addColorStop(1, "rgba(4, 14, 28, 1)");
  context.fillStyle = fill;
  context.beginPath();
  context.arc(cx, cy, radius, 0, Math.PI * 2);
  context.fill();
}

function drawAtmosphere(context: CanvasRenderingContext2D, cx: number, cy: number, radius: number) {
  context.save();
  context.strokeStyle = "rgba(104, 202, 255, 0.18)";
  context.lineWidth = radius * 0.09;
  context.beginPath();
  context.arc(cx, cy, radius + radius * 0.03, 0, Math.PI * 2);
  context.stroke();
  context.strokeStyle = "rgba(244, 184, 96, 0.28)";
  context.lineWidth = 1.25;
  context.beginPath();
  context.arc(cx, cy, radius, 0, Math.PI * 2);
  context.stroke();
  context.restore();
}

function drawGrid(
  context: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  radius: number,
  rotation: { lon: number; lat: number }
) {
  context.lineWidth = 1;
  context.strokeStyle = "rgba(74, 184, 217, 0.28)";

  for (const lat of PARALLELS) {
    drawLine(context, cx, cy, radius, rotation, buildParallel(lat));
  }

  for (const lon of MERIDIANS) {
    drawLine(context, cx, cy, radius, rotation, buildMeridian(lon));
  }
}

function drawMarkers(
  context: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  radius: number,
  markers: GlobeMarker[],
  rotation: { lon: number; lat: number },
  selectedId?: string | null
) {
  return markers.map((marker) => {
    const projected = projectPoint(marker.lat, marker.lon, rotation, cx, cy, radius);

    if (!projected.visible) {
      return { id: marker.id, x: projected.x, y: projected.y, r: 0, visible: false };
    }

    const size = marker.selected || marker.id === selectedId ? marker.size + 2.5 : marker.size;
    const alpha = 0.45 + projected.depth * 0.55;

    context.save();
    context.fillStyle = marker.color.replace("1)", `${alpha})`);
    context.shadowColor = marker.selected || marker.id === selectedId ? "rgba(244, 184, 96, 0.9)" : marker.color;
    context.shadowBlur = marker.selected || marker.id === selectedId ? 18 : 10;
    context.beginPath();
    context.arc(projected.x, projected.y, size, 0, Math.PI * 2);
    context.fill();
    context.restore();

    if (marker.selected || marker.id === selectedId) {
      context.save();
      context.strokeStyle = "rgba(255, 231, 191, 0.95)";
      context.lineWidth = 1.5;
      context.beginPath();
      context.arc(projected.x, projected.y, size + 6, 0, Math.PI * 2);
      context.stroke();
      context.restore();
    }

    return { id: marker.id, x: projected.x, y: projected.y, r: size, visible: true };
  });
}

function drawLine(
  context: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  radius: number,
  rotation: { lon: number; lat: number },
  points: Array<{ lat: number; lon: number }>
) {
  let started = false;
  context.beginPath();

  for (const point of points) {
    const projected = projectPoint(point.lat, point.lon, rotation, cx, cy, radius);
    if (!projected.visible) {
      started = false;
      continue;
    }
    if (!started) {
      context.moveTo(projected.x, projected.y);
      started = true;
    } else {
      context.lineTo(projected.x, projected.y);
    }
  }

  context.stroke();
}

function buildParallel(lat: number) {
  const points: Array<{ lat: number; lon: number }> = [];
  for (let lon = -180; lon <= 180; lon += 4) {
    points.push({ lat, lon });
  }
  return points;
}

function buildMeridian(lon: number) {
  const points: Array<{ lat: number; lon: number }> = [];
  for (let lat = -90; lat <= 90; lat += 4) {
    points.push({ lat, lon });
  }
  return points;
}

function projectPoint(
  lat: number,
  lon: number,
  rotation: { lon: number; lat: number },
  cx: number,
  cy: number,
  radius: number
) {
  const latRad = toRadians(lat);
  const lonRad = toRadians(lon + rotation.lon);
  const rotX = toRadians(rotation.lat);

  const x0 = Math.cos(latRad) * Math.sin(lonRad);
  const y0 = Math.sin(latRad);
  const z0 = Math.cos(latRad) * Math.cos(lonRad);

  const y = y0 * Math.cos(rotX) - z0 * Math.sin(rotX);
  const z = y0 * Math.sin(rotX) + z0 * Math.cos(rotX);
  const x = x0;

  return {
    x: cx + x * radius,
    y: cy - y * radius,
    depth: (z + 1) / 2,
    visible: z > -0.08
  };
}

function toRadians(value: number) {
  return (value * Math.PI) / 180;
}
