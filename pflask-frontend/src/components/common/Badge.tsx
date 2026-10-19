import React from "react";

interface BadgeProps {
  children: React.ReactNode;
  variant?: "primary" | "success" | "warning" | "info" | "neutral";
}

export const Badge: React.FC<BadgeProps> = ({ children, variant = "neutral" }) => {
  const styles: Record<string, { bg: string; color: string; border: string }> = {
    primary: { bg: "rgba(15, 127, 130, 0.12)", color: "#0F3F3F", border: "1px solid rgba(15, 127, 130, 0.4)" },
    success: { bg: "rgba(22, 163, 74, 0.12)", color: "#15803D", border: "1px solid rgba(22, 163, 74, 0.4)" },
    warning: { bg: "rgba(202, 138, 4, 0.12)", color: "#A16207", border: "1px solid rgba(202, 138, 4, 0.4)" },
    info: { bg: "rgba(37, 99, 235, 0.12)", color: "#1D4ED8", border: "1px solid rgba(37, 99, 235, 0.4)" },
    neutral: { bg: "#f1f1f4", color: "#6b7280", border: "1px solid #e5e7eb" },
  };

  const current = styles[variant] || styles.neutral;

  return (
    <span
      style={{
        display: "inline-block",
        padding: "3px 8px",
        borderRadius: "4px",
        fontSize: "0.8rem",
        fontWeight: 600,
        backgroundColor: current.bg,
        color: current.color,
        border: current.border,
        fontFamily: "sans-serif",
      }}
    >
      {children}
    </span>
  );
};

export default Badge;
