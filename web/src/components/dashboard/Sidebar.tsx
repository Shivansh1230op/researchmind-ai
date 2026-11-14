"use client";
import { useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { Brain, LayoutDashboard, FileText, MessageSquare, FolderTree, GitCompare, History, BarChart3, Settings, Network, NotebookPen, AlignLeft, PanelLeftClose, PanelLeftOpen, ArrowUpRight } from "lucide-react";
const items = [
  ["Overview", "/dashboard", LayoutDashboard], ["AI Research Chat", "/dashboard/workspace", MessageSquare],
  ["Document Library", "/dashboard/documents", FileText], ["Workspaces", "/dashboard/collections", FolderTree],
  ["Research Analysis", "/dashboard/compare", GitCompare], ["Knowledge Graph", "/dashboard/graph", Network],
  ["AI Summarizer", "/dashboard/summarize", AlignLeft], ["Research Reports", "/dashboard/reports", NotebookPen],
  ["Conversation History", "/dashboard/history", History], ["Analytics", "/dashboard/analytics", BarChart3],
  ["Settings", "/dashboard/settings", Settings],
] as const;
export default function Sidebar() {
  const path = usePathname(); const [collapsed, setCollapsed] = useState(false);
  return <aside className={`research-sidebar ${collapsed ? "collapsed" : ""}`}>
    <Link href="/" className="brand"><span className="brand-symbol"><Brain size={22} /></span><span className="sidebar-label">ResearchMind<span className="brand-ai"> AI</span><small>YOUR INTELLIGENCE WORKSPACE</small></span></Link>
    <div className="sidebar-section sidebar-label">WORKSPACE</div><nav>{items.map(([label, href, Icon]) => <Link key={href} href={href} title={label} className={`nav-item ${path === href ? "active" : ""}`}><Icon size={17} /><span className="sidebar-label">{label}</span>{path === href && <i />}</Link>)}</nav>
    <div className="sidebar-bottom"><div className="sidebar-note sidebar-label"><span className="eyebrow">YOUR NEXT BREAKTHROUGH</span><p>Less searching.<br />More understanding.</p><Link href="/dashboard/workspace">Start researching <ArrowUpRight size={14} /></Link></div><button className="collapse-button" onClick={() => setCollapsed(!collapsed)} aria-label="Toggle sidebar">{collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}<span className="sidebar-label">Collapse sidebar</span></button></div>
  </aside>;
}
