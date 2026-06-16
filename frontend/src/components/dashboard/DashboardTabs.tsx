/**
 * DashboardTabs — tab navigation for Step 6 report views (T-5.4).
 */

import { useState, type JSX, type ReactNode } from "react";

export type DashboardTabId = "catalog" | "families" | "metrics";

interface TabDef {
  id: DashboardTabId;
  label: string;
}

const TABS: TabDef[] = [
  { id: "catalog", label: "Salud del Catálogo" },
  { id: "families", label: "Errores por Familia" },
  { id: "metrics", label: "Métricas" },
];

interface Props {
  panels: Record<DashboardTabId, ReactNode>;
  defaultTab?: DashboardTabId;
}

export function DashboardTabs({
  panels,
  defaultTab = "catalog",
}: Props): JSX.Element {
  const [activeTab, setActiveTab] = useState<DashboardTabId>(defaultTab);

  return (
    <div style={styles.wrapper}>
      <div style={styles.tabs} role="tablist" aria-label="Vistas del informe">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`dashboard-tab-${tab.id}`}
            aria-selected={activeTab === tab.id}
            aria-controls={`dashboard-panel-${tab.id}`}
            style={{
              ...styles.tab,
              ...(activeTab === tab.id ? styles.tabActive : {}),
            }}
            onClick={() => setActiveTab(tab.id)}
            data-testid={`dashboard-tab-${tab.id}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {TABS.map((tab) => (
        <div
          key={tab.id}
          role="tabpanel"
          id={`dashboard-panel-${tab.id}`}
          aria-labelledby={`dashboard-tab-${tab.id}`}
          hidden={activeTab !== tab.id}
          style={styles.panel}
          data-testid={`dashboard-panel-${tab.id}`}
        >
          {activeTab === tab.id ? panels[tab.id] : null}
        </div>
      ))}
    </div>
  );
}

const styles = {
  wrapper: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "16px",
  },
  tabs: {
    display: "flex",
    gap: "4px",
    borderBottom: "2px solid var(--color-border)",
  },
  tab: {
    padding: "8px 20px",
    fontSize: "var(--font-size-sm)",
    fontWeight: 500,
    border: "none",
    borderBottom: "2px solid transparent",
    backgroundColor: "transparent",
    cursor: "pointer",
    color: "var(--color-text-muted)",
    marginBottom: "-2px",
    transition: "color 0.15s, border-color 0.15s",
  },
  tabActive: {
    color: "var(--color-primary)",
    borderBottom: "2px solid var(--color-primary)",
    fontWeight: 600,
  },
  panel: {
    backgroundColor: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    borderRadius: "var(--radius-md)",
    padding: "20px",
  },
} as const;
