"use client";

import { useState } from "react";

/**
 * Proballers sirve el escudo de cada equipo en una URL predecible a partir
 * de su id (el mismo id que usamos como clave primaria en `teams`), sin
 * necesidad de scrapearlo ni guardarlo aparte:
 *   https://www.proballers.com/media/team/<id>.svg
 */
export function teamLogoUrl(teamId: number): string {
  return `https://www.proballers.com/media/team/${teamId}.svg`;
}

export function TeamLogo({
  teamId,
  name,
  size = 24,
}: {
  teamId: number;
  name: string;
  size?: number;
}) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <span
        className="team-badge"
        style={{
          width: size,
          height: size,
          fontSize: Math.max(9, size * 0.34),
          borderRadius: Math.max(4, size * 0.26),
          flexShrink: 0,
        }}
      >
        {name.slice(0, 2).toUpperCase()}
      </span>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={teamLogoUrl(teamId)}
      alt=""
      width={size}
      height={size}
      style={{ width: size, height: size, objectFit: "contain", flexShrink: 0 }}
      onError={() => setFailed(true)}
      loading="lazy"
    />
  );
}

/** Logo + nombre en línea, para usar dentro de tablas, tarjetas, etc. */
export function TeamInline({
  teamId,
  name,
  size = 22,
  href,
  bold = false,
}: {
  teamId: number;
  name: string;
  size?: number;
  href?: string;
  bold?: boolean;
}) {
  const content = (
    <span className="team-inline">
      <TeamLogo teamId={teamId} name={name} size={size} />
      <span style={{ fontWeight: bold ? 600 : undefined }}>{name}</span>
    </span>
  );
  return href ? <a href={href}>{content}</a> : content;
}
