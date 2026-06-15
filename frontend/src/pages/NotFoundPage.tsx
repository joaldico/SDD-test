import type { JSX } from "react";
import { Link } from "react-router-dom";

export function NotFoundPage(): JSX.Element {
  return (
    <div style={styles.page}>
      <h1 style={styles.code}>404</h1>
      <p style={styles.message}>Página no encontrada.</p>
      <Link to="/" style={styles.link}>Volver al Dashboard</Link>
    </div>
  );
}

const styles = {
  page: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    justifyContent: "center",
    height: "100%",
    gap: "12px",
    color: "var(--color-text-muted)",
  },
  code: {
    fontSize: "64px",
    fontWeight: 700,
    color: "var(--color-text)",
  },
  message: {
    fontSize: "16px",
  },
  link: {
    fontSize: "14px",
    color: "var(--color-primary)",
    textDecoration: "underline",
  },
} as const;
