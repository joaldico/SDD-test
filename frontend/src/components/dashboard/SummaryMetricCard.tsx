import type { JSX } from "react";

interface Props {
  label: string;
  value: number;
  color: string;
  testId: string;
}

export function SummaryMetricCard({
  label,
  value,
  color,
  testId,
}: Props): JSX.Element {
  return (
    <div
      style={{ ...styles.card, borderTopColor: color }}
      data-testid={testId}
    >
      <span style={{ ...styles.value, color }}>{value.toLocaleString()}</span>
      <span style={styles.label}>{label}</span>
    </div>
  );
}

const styles = {
  card: {
    backgroundColor: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    borderTop: "4px solid",
    borderRadius: "var(--radius-md)",
    padding: "20px",
    display: "flex",
    flexDirection: "column" as const,
    gap: "6px",
  },
  value: {
    fontSize: "28px",
    fontWeight: 700,
    lineHeight: 1.1,
  },
  label: {
    fontSize: "13px",
    color: "var(--color-text-muted)",
  },
} as const;
