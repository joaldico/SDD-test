import type { JSX } from "react";
import { NavLink } from "react-router-dom";

interface NavItem {
  path: string;
  label: string;
  icon: string;
  /** Routes not yet implemented — rendered but not clickable */
  comingSoon?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { path: "/",               label: "Dashboard",      icon: "▣" },
  { path: "/conciliacion",   label: "Conciliación",   icon: "⇄" },
  { path: "/historico",      label: "Histórico",      icon: "◷", comingSoon: true },
  { path: "/admin",          label: "Administración", icon: "⚙", comingSoon: true },
];

export function Sidebar(): JSX.Element {
  return (
    <aside style={styles.aside}>
      {/* Brand header */}
      <div style={styles.header}>
        <span style={styles.brandIcon}>◈</span>
        <span style={styles.brandName}>Conciliador</span>
      </div>

      {/* Module navigation */}
      <nav aria-label="Módulos" style={styles.nav}>
        <ul style={styles.list}>
          {NAV_ITEMS.map((item) =>
            item.comingSoon ? (
              <li key={item.path} style={styles.itemWrapper}>
                <span style={{ ...styles.link, ...styles.linkDisabled }}>
                  <span style={styles.icon}>{item.icon}</span>
                  <span style={styles.label}>{item.label}</span>
                  <span style={styles.badge}>Próximamente</span>
                </span>
              </li>
            ) : (
              <li key={item.path} style={styles.itemWrapper}>
                <NavLink
                  to={item.path}
                  end
                  style={({ isActive }) =>
                    isActive
                      ? { ...styles.link, ...styles.linkActive }
                      : styles.link
                  }
                >
                  <span style={styles.icon}>{item.icon}</span>
                  <span style={styles.label}>{item.label}</span>
                </NavLink>
              </li>
            )
          )}
        </ul>
      </nav>

      {/* Footer */}
      <div style={styles.footer}>
        <span style={styles.version}>v0.3.0 · M3</span>
      </div>
    </aside>
  );
}

const styles = {
  aside: {
    width: "var(--sidebar-width)",
    minWidth: "var(--sidebar-width)",
    height: "100%",
    backgroundColor: "var(--sidebar-bg)",
    display: "flex",
    flexDirection: "column" as const,
    borderRight: "1px solid rgba(255,255,255,0.06)",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: "var(--space-3)",
    padding: "var(--space-5) var(--space-4)",
    borderBottom: "1px solid rgba(255,255,255,0.08)",
  },
  brandIcon: {
    fontSize: "22px",
    color: "var(--color-primary)",
    lineHeight: 1,
  },
  brandName: {
    fontSize: "16px",
    fontWeight: "var(--font-weight-bold)" as unknown as number,
    color: "var(--sidebar-text-active)",
    letterSpacing: "0.01em",
  },
  nav: {
    flex: 1,
    overflowY: "auto" as const,
    padding: "var(--space-3) 0",
  },
  list: {
    listStyle: "none",
    display: "flex",
    flexDirection: "column" as const,
    gap: "var(--space-1)",
    padding: "0 var(--space-3)",
  },
  itemWrapper: {
    display: "block",
  },
  link: {
    display: "flex",
    alignItems: "center",
    gap: "var(--space-3)",
    padding: "var(--space-2) var(--space-3)",
    borderRadius: "var(--radius-sm)",
    fontSize: "var(--font-size-sm)",
    color: "var(--sidebar-text)",
    cursor: "pointer",
    transition: "background 0.15s, color 0.15s",
    userSelect: "none" as const,
  },
  linkActive: {
    backgroundColor: "var(--sidebar-active-bg)",
    color: "var(--sidebar-text-active)",
    fontWeight: "var(--font-weight-medium)" as unknown as number,
  },
  linkDisabled: {
    opacity: 0.5,
    cursor: "not-allowed",
  },
  icon: {
    fontSize: "15px",
    width: "18px",
    textAlign: "center" as const,
    flexShrink: 0,
  },
  label: {
    flex: 1,
  },
  badge: {
    fontSize: "var(--font-size-xs)",
    backgroundColor: "rgba(255,255,255,0.1)",
    color: "var(--sidebar-text)",
    padding: "1px 6px",
    borderRadius: "var(--radius-sm)",
    whiteSpace: "nowrap" as const,
  },
  footer: {
    padding: "var(--space-4)",
    borderTop: "1px solid rgba(255,255,255,0.06)",
  },
  version: {
    fontSize: "var(--font-size-xs)",
    color: "var(--color-text-disabled)",
  },
} as const;
