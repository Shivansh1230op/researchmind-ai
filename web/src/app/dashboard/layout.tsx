import Sidebar from "@/components/dashboard/Sidebar";
import TopBar from "@/components/dashboard/TopBar";
import AuthGate from "@/components/dashboard/AuthGate";

/**
 * Dashboard layout — wraps all authenticated application pages.
 *
 * Structure:
 *   ┌─────────────┬──────────────────────────┐
 *   │             │  TopBar                   │
 *   │  Sidebar    ├──────────────────────────┤
 *   │             │                          │
 *   │             │  Page Content            │
 *   │             │                          │
 *   └─────────────┴──────────────────────────┘
 */
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGate><div className="dashboard-shell flex h-screen overflow-hidden bg-[var(--bg-base)]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div></AuthGate>
  );
}
