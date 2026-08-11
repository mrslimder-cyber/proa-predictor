"use client";

import { useRouter } from "next/navigation";

export default function TeamSwitcher({
  season,
  teams,
  current,
}: {
  season: string;
  teams: { id: number; name: string }[];
  current: number;
}) {
  const router = useRouter();

  return (
    <select
      className="season-select"
      value={current}
      onChange={(e) =>
        router.push(`/temporadas/${encodeURIComponent(season)}/equipos/${e.target.value}`)
      }
    >
      {teams.map((t) => (
        <option key={t.id} value={t.id}>
          {t.name}
        </option>
      ))}
    </select>
  );
}
