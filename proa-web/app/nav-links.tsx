"use client";

import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Próximos partidos" },
  { href: "/temporadas", label: "Temporadas" },
  { href: "/clasificacion", label: "Ranking Elo" },
  { href: "/evolucion", label: "Evolución" },
];

export default function NavLinks() {
  const pathname = usePathname();

  return (
    <nav className="mainnav">
      {LINKS.map((link) => {
        const active =
          link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
        return (
          <a key={link.href} href={link.href} className={active ? "active" : ""}>
            {link.label}
          </a>
        );
      })}
    </nav>
  );
}
