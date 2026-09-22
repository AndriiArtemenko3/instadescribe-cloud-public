import * as React from 'react'
import { NavLink } from 'react-router-dom'
import {
  Home, FolderOpen, BarChart2, HelpCircle, Settings,
  ChevronRight,
} from 'lucide-react'
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenuSub,
  SidebarMenuSubItem,
  SidebarMenuSubButton,
} from '@/components/ui/sidebar'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { NavMain } from '@/components/nav-main'
import { Logo } from '@/components/ui/Logo'
import { useAppStore } from '@/store/appStore'
import type { Project } from '@/types'

const navItems = [
  { title: 'Home', url: '/dashboard', icon: Home },
  { title: 'Projects', url: '/dashboard/projects', icon: FolderOpen },
  { title: 'Usage', url: '/dashboard/usage', icon: BarChart2 },
  { title: 'Help', url: '/dashboard/help', icon: HelpCircle },
  { title: 'Settings', url: '/dashboard/settings', icon: Settings },
]

const RECENT_LIMIT = 8

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const projects = useAppStore((s) => s.projects)

  const recentSorted = React.useMemo(
    () => [...projects].sort(
      (a, b) => +new Date(b.createdAt) - +new Date(a.createdAt),
    ),
    [projects],
  )
  const recent = recentSorted.slice(0, RECENT_LIMIT)
  const hasMore = recentSorted.length > RECENT_LIMIT
  const starred = React.useMemo(
    () => projects.filter((p) => p.starred),
    [projects],
  )

  return (
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader className="flex h-14 items-center justify-center border-b">
        <Logo size={20} className="text-brand-400" />
      </SidebarHeader>
      <SidebarContent className="flex-1">
        <NavMain items={navItems} />

        <div className="mx-3 my-1 h-px bg-sidebar-border" aria-hidden="true" />

        <ProjectGroup label="Starred" items={starred} emptyText="No starred projects yet" />

        <ProjectGroup label="Recent" items={recent} emptyText="No projects yet">
          {hasMore && (
            <SidebarMenuSubItem>
              <SidebarMenuSubButton render={<NavLink to="/dashboard/projects" />} className="italic text-sidebar-foreground/60">
                <span>… see more</span>
              </SidebarMenuSubButton>
            </SidebarMenuSubItem>
          )}
        </ProjectGroup>
      </SidebarContent>
    </Sidebar>
  )
}

function ProjectGroup({
  label,
  items,
  emptyText,
  children,
}: {
  label: string
  items: Project[]
  emptyText: string
  children?: React.ReactNode
}) {
  return (
    <SidebarGroup className="px-2 py-1">
      <Collapsible defaultOpen>
        <SidebarGroupLabel
          render={<CollapsibleTrigger />}
          className="flex w-full cursor-pointer items-center text-sm font-semibold text-sidebar-foreground"
        >
          <span>{label}</span>
          <ChevronRight className="ml-auto h-3.5 w-3.5 transition-transform [[data-panel-open]_&]:rotate-90" />
        </SidebarGroupLabel>
        <CollapsibleContent className="overflow-hidden h-[var(--collapsible-panel-height)] transition-[height] duration-200 ease-[cubic-bezier(0.05,0.7,0.1,1)] data-[starting-style]:h-0 data-[ending-style]:h-0">
          <SidebarMenuSub>
            {items.length === 0 ? (
              <SidebarMenuSubItem>
                <span className="px-2 py-1 text-xs italic text-sidebar-foreground/60">
                  {emptyText}
                </span>
              </SidebarMenuSubItem>
            ) : items.map((p) => (
              <SidebarMenuSubItem key={p.id}>
                <SidebarMenuSubButton render={<NavLink to={`/editor/${p.id}`} />}>
                  <span>{p.name}</span>
                </SidebarMenuSubButton>
              </SidebarMenuSubItem>
            ))}
            {children}
          </SidebarMenuSub>
        </CollapsibleContent>
      </Collapsible>
    </SidebarGroup>
  )
}
