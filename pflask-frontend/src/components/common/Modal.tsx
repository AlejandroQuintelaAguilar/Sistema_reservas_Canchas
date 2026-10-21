import React, { useEffect } from "react";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  maxWidth?: string;
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  maxWidth = "550px",
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    if (isOpen) {
      document.body.style.overflow = "hidden";
      window.addEventListener("keydown", handleKeyDown);
    } else {
      document.body.style.overflow = "unset";
    }
    return () => {
      document.body.style.overflow = "unset";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0, 0, 0, 0.65)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        padding: "1rem",
        fontFamily: "sans-serif",
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: "var(--color-surface, #ffffff)",
          color: "var(--color-text, #111827)",
          borderRadius: "12px",
          width: "100%",
          maxWidth,
          maxHeight: "92vh",
          overflowY: "auto",
          boxShadow: "var(--shadow-lg, 0 20px 60px rgba(17, 24, 39, 0.18))",
          border: "1px solid var(--color-border, #e5e7eb)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "15px 20px",
            borderBottom: "1px solid var(--color-border, #e5e7eb)",
          }}
        >
          <h3
            style={{
              margin: 0,
              fontSize: "1.2rem",
              fontWeight: 600,
              color: "var(--color-text, #111827)",
            }}
          >
            {title}
          </h3>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: "var(--color-text-dim, #6b7280)",
              fontSize: "1.5rem",
              cursor: "pointer",
              lineHeight: 1,
              padding: "0 5px",
            }}
          >
            &times;
          </button>
        </div>
        <div style={{ padding: "20px" }}>{children}</div>
      </div>
    </div>
  );
};

export default Modal;
