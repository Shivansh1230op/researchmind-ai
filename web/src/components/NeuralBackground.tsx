"use client";

import { useEffect, useRef } from "react";

/**
 * NeuralBackground — animated neural network canvas.
 *
 * Renders a subtle network of nodes connected by lines on a dark background.
 * Nodes drift slowly and connections glow when nodes are near each other.
 * Mouse position creates a gentle attraction field.
 *
 * Performance: capped at 80 nodes, uses requestAnimationFrame,
 * respects prefers-reduced-motion, pauses when tab is hidden.
 */
export default function NeuralBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const element = canvasRef.current;
    if (!element) return;
    const canvas: HTMLCanvasElement = element;
    const context = canvas.getContext("2d");
    if (!context) return;
    const ctx: CanvasRenderingContext2D = context;

    // Check reduced motion preference
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    let width = 0;
    let height = 0;
    let animationId = 0;

    // Node interface
    interface Node {
      x: number;
      y: number;
      vx: number;
      vy: number;
      radius: number;
      pulse: number;
    }

    let nodes: Node[] = [];
    const mouse = { x: -1000, y: -1000 };
    const MAX_NODES = 70;
    const MAX_DISTANCE = 160;

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = canvas.parentElement?.clientWidth ?? window.innerWidth;
      height = canvas.parentElement?.clientHeight ?? window.innerHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.scale(dpr, dpr);
    }

    function initNodes() {
      nodes = [];
      for (let i = 0; i < MAX_NODES; i++) {
        nodes.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.3,
          vy: (Math.random() - 0.5) * 0.3,
          radius: Math.random() * 1.5 + 0.5,
          pulse: Math.random() * Math.PI * 2,
        });
      }
    }

    function draw() {
      ctx.clearRect(0, 0, width, height);

      // Draw connections
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < MAX_DISTANCE) {
            const opacity = (1 - dist / MAX_DISTANCE) * 0.15;
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.strokeStyle = `rgba(34, 211, 238, ${opacity})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }

      // Draw nodes
      for (const node of nodes) {
        node.pulse += 0.01;
        const pulseRadius = node.radius + Math.sin(node.pulse) * 0.3;

        // Mouse interaction — subtle attraction
        const mdx = mouse.x - node.x;
        const mdy = mouse.y - node.y;
        const mdist = Math.sqrt(mdx * mdx + mdy * mdy);
        if (mdist < 200) {
          const force = (1 - mdist / 200) * 0.02;
          node.vx += (mdx / mdist) * force;
          node.vy += (mdy / mdist) * force;
        }

        // Draw glow
        const glow = ctx.createRadialGradient(
          node.x, node.y, 0,
          node.x, node.y, pulseRadius * 4
        );
        glow.addColorStop(0, "rgba(34, 211, 238, 0.15)");
        glow.addColorStop(1, "rgba(34, 211, 238, 0)");
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(node.x, node.y, pulseRadius * 4, 0, Math.PI * 2);
        ctx.fill();

        // Draw node
        ctx.beginPath();
        ctx.arc(node.x, node.y, pulseRadius, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(34, 211, 238, 0.5)";
        ctx.fill();

        // Update position
        node.x += node.vx;
        node.y += node.vy;

        // Damping
        node.vx *= 0.99;
        node.vy *= 0.99;

        // Wrap edges
        if (node.x < 0) node.x = width;
        if (node.x > width) node.x = 0;
        if (node.y < 0) node.y = height;
        if (node.y > height) node.y = 0;
      }

      animationId = requestAnimationFrame(draw);
    }

    function onMouseMove(e: MouseEvent) {
      const rect = canvas.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
    }

    function onMouseLeave() {
      mouse.x = -1000;
      mouse.y = -1000;
    }

    function onVisibility() {
      if (document.hidden) {
        cancelAnimationFrame(animationId);
      } else if (!prefersReducedMotion) {
        animationId = requestAnimationFrame(draw);
      }
    }

    resize();
    initNodes();

    if (prefersReducedMotion) {
      // Draw a single static frame
      draw();
      cancelAnimationFrame(animationId);
    } else {
      animationId = requestAnimationFrame(draw);
    }

    window.addEventListener("resize", () => {
      resize();
      initNodes();
    });
    window.addEventListener("mousemove", onMouseMove);
    canvas.addEventListener("mouseleave", onMouseLeave);
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMouseMove);
      canvas.removeEventListener("mouseleave", onMouseLeave);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 h-full w-full"
      aria-hidden="true"
    />
  );
}
