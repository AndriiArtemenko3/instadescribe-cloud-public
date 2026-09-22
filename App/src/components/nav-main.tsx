import { NavLink, useMatch, useResolvedPath } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import {
  SidebarGroup,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'

interface NavItem {
  title: string
  url: string
  icon: LucideIcon
}

interface NavMainProps {
  items: NavItem[]
}

function NavItemButton({ item }: { item: NavItem }) {
  const resolved = useResolvedPath(item.url)
  const match = useMatch({ path: resolved.pathname, end: true })

  return (
    <SidebarMenuItem>
      <SidebarMenuButton render={<NavLink to={item.url} end />} isActive={!!match} tooltip={item.title}>
        <item.icon />
        <span>{item.title}</span>
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}

export function NavMain({ items }: NavMainProps) {
  return (
    <SidebarGroup>
      <SidebarMenu>
        {items.map((item) => (
          <NavItemButton key={item.title} item={item} />
        ))}
      </SidebarMenu>
    </SidebarGroup>
  )
}
