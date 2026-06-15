import type { JSX } from "react";

export function DashboardPage(): JSX.Element {
  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <h1 style={styles.title}>Dashboard</h1>
        <p style={styles.subtitle}>
          Bienvenido al Conciliador de Errores de Publicación Marketplace.
        </p>
      </header>

      <div style={styles.grid}>
        <ModuleCard
          title="Nueva Conciliación"
          description="Carga tus tres ficheros (Libro1, fullstock, processing-summary) e inicia el proceso de conciliación."
          status="coming-soon"
        />
        <ModuleCard
          title="Histórico"
          description="Consulta el resultado de conciliaciones anteriores y descarga los informes exportados."
          status="coming-soon"
        />
        <ModuleCard
          title="Taxonomía de Errores"
          description="Gestiona las familias y códigos de error del catálogo. Reasigna códigos desconocidos."
          status="coming-soon"
        />
      </div>
    </div>
  );
}

interface ModuleCardProps {
  title: string;
  description: string;
  status: "ready" | "coming-soon";
}

function ModuleCard({ title, description, status }: ModuleCardProps): JSX.Element {
  return (
    <article style={styles.card}>
      <div style={styles.cardHeader}>
        <h2 style={styles.cardTitle}>{title}</h2>
        {status === "coming-soon" && (
          <span style={styles.cardBadge}>Próximamente</span>
        )}
      </div>
      <p style={styles.cardDescription}>{description}</p>
    </article>
  );
}

const styles = {
  page: {
    padding: "32px",
    maxWidth: "900px",
  },
  header: {
    marginBottom: "32px",
  },
  title: {
    fontSize: "24px",
    fontWeight: 700,
    color: "var(--color-text)",
    marginBottom: "8px",
  },
  subtitle: {
    fontSize: "15px",
    color: "var(--color-text-muted)",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
    gap: "20px",
  },
  card: {
    backgroundColor: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    borderRadius: "var(--radius-md)",
    padding: "20px",
  },
  cardHeader: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: "12px",
    marginBottom: "10px",
  },
  cardTitle: {
    fontSize: "15px",
    fontWeight: 600,
    color: "var(--color-text)",
  },
  cardBadge: {
    fontSize: "11px",
    backgroundColor: "var(--color-primary-light)",
    color: "var(--color-primary)",
    padding: "2px 8px",
    borderRadius: "4px",
    whiteSpace: "nowrap" as const,
    flexShrink: 0,
  },
  cardDescription: {
    fontSize: "13px",
    color: "var(--color-text-muted)",
    lineHeight: 1.6,
  },
} as const;
