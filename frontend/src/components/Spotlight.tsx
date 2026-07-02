import { useRef, useState, type CSSProperties } from "react";

interface Props {
  children: React.ReactNode;
  className?: string;
  glow?: string;
}

export function Spotlight({
  children,
  className = "",
  glow = "rgba(78, 161, 255, 0.18)",
}: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);

  return (
    <div
      ref={ref}
      onMouseMove={(e) => {
        const r = ref.current?.getBoundingClientRect();
        if (!r) return;
        setPos({ x: e.clientX - r.left, y: e.clientY - r.top });
      }}
      onMouseLeave={() => setPos(null)}
      className={`relative overflow-hidden ${className}`}
      style={
        pos
          ? ({
              "--mx": `${pos.x}px`,
              "--my": `${pos.y}px`,
              "--glow": glow,
            } as CSSProperties)
          : undefined
      }
    >
      {pos && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 transition-opacity duration-300"
          style={{
            background:
              "radial-gradient(260px circle at var(--mx) var(--my), var(--glow), transparent 72%)",
            opacity: 0.9,
          }}
        />
      )}
      {children}
    </div>
  );
}
