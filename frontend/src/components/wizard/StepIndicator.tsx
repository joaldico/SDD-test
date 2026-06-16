import type { JSX } from "react";

interface Step {
  label: string;
  description: string;
}

const STEPS: Step[] = [
  { label: "1", description: "Carga de ficheros" },
  { label: "2", description: "Selección de hoja" },
  { label: "3", description: "Mapeo de columnas" },
  { label: "4", description: "Resumen" },
  { label: "5", description: "Procesando" },
];

interface Props {
  currentStep: 1 | 2 | 3 | 4 | 5;
}

export function StepIndicator({ currentStep }: Props): JSX.Element {
  return (
    <nav aria-label="Pasos del asistente" style={styles.container}>
      {STEPS.map((step, idx) => {
        const stepNum = (idx + 1) as 1 | 2 | 3 | 4 | 5;
        const isCompleted = stepNum < currentStep;
        const isActive = stepNum === currentStep;

        return (
          <div key={step.label} style={styles.stepRow}>
            {/* Connector line before step (except first) */}
            {idx > 0 && (
              <div
                style={{
                  ...styles.connector,
                  backgroundColor: isCompleted
                    ? "var(--color-primary)"
                    : "var(--color-border)",
                }}
              />
            )}

            {/* Circle + label */}
            <div style={styles.stepItem}>
              <div
                style={{
                  ...styles.circle,
                  ...(isCompleted ? styles.circleCompleted : {}),
                  ...(isActive ? styles.circleActive : {}),
                  ...(!isActive && !isCompleted ? styles.circleIdle : {}),
                }}
                aria-current={isActive ? "step" : undefined}
              >
                {isCompleted ? "✓" : step.label}
              </div>
              <span
                style={{
                  ...styles.description,
                  ...(isActive ? styles.descriptionActive : {}),
                }}
              >
                {step.description}
              </span>
            </div>
          </div>
        );
      })}
    </nav>
  );
}

const styles = {
  container: {
    display: "flex",
    alignItems: "center",
    gap: 0,
    padding: "0 0 32px 0",
  },
  stepRow: {
    display: "flex",
    alignItems: "center",
    flex: 1,
  },
  connector: {
    flex: 1,
    height: "2px",
    minWidth: "24px",
    transition: "background-color 0.25s",
  },
  stepItem: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    gap: "6px",
    flexShrink: 0,
  },
  circle: {
    width: "32px",
    height: "32px",
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "13px",
    fontWeight: 600,
    transition: "background 0.25s, color 0.25s, border-color 0.25s",
    border: "2px solid transparent",
  },
  circleIdle: {
    backgroundColor: "var(--color-surface)",
    border: "2px solid var(--color-border)",
    color: "var(--color-text-disabled)",
  },
  circleActive: {
    backgroundColor: "var(--color-primary)",
    border: "2px solid var(--color-primary)",
    color: "#fff",
  },
  circleCompleted: {
    backgroundColor: "var(--color-primary)",
    border: "2px solid var(--color-primary)",
    color: "#fff",
  },
  description: {
    fontSize: "var(--font-size-xs)",
    color: "var(--color-text-muted)",
    whiteSpace: "nowrap" as const,
    textAlign: "center" as const,
  },
  descriptionActive: {
    color: "var(--color-primary)",
    fontWeight: 600,
  },
} as const;
