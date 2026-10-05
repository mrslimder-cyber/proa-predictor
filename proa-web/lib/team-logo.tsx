"use client";

import { useState } from "react";

const RGM = "https://basketball.realgm.com/images/basketball/5.0/team_logos/international/german";

// id de equipo en RealGM -> archivo de logo. Los equipos sin logo en RealGM
// (Koblenz, Orange Academy, Karlsruhe, Köln, Wolmirstedt, Bochum...) caen a iniciales.
const LOGO_FILES: Record<number, string> = {
  679: "artland.jpg",
  686: "bbc.jpg",
  681: "bg.jpg",
  1380: "kircheim.png",
  377: "bremerhaven.jpg",
  1378: "wohnbau.png",
  1085: "finke.png",
  685: "46ers.jpg",
  215: "crailsheim.png",
  1376: "mlp.png",
  1375: "nuernberger.png",
  684: "tigers.jpg",
};

// id de equipo -> archivo en proa-web/public/logos/ (logos propios, tienen
// prioridad sobre los de RealGM). Añade una línea por cada equipo nuevo:
//   1665: "koeln.png",
const LOCAL_LOGOS: Record<number, string> = {
  1665: "koeln.png",
  2309: "klobenz.png",
  2258: "wolmirstedt.png",
  1567: "sparkassenstars.png",
  1578: "ratiopharm.png",
  1763: "lions.png",
};

export function teamLogoUrl(teamId: number): string | null {
  const local = LOCAL_LOGOS[teamId];
  if (local) return `/logos/${local}`;
  const file = LOGO_FILES[teamId];
  return file ? `${RGM}/${file}` : null;
}

function initials(name: string): string {
  const words = name.split(/\s+/).filter(Boolean);
  if (words[0] && words[0] === words[0].toUpperCase() && words[0].length <= 4) {
    return words[0].slice(0, 3);
  }
  return words.slice(0, 2).map((w) => w[0]).join("").toUpperCase();
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
  const url = teamLogoUrl(teamId);

  if (!url || failed) {
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
        {initials(name)}
      </span>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt=""
      width={size}
      height={size}
      style={{ width: size, height: size, objectFit: "contain", flexShrink: 0 }}
      onError={() => setFailed(true)}
      referrerPolicy="no-referrer"
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