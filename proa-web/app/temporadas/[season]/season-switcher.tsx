"use client";

import { useRouter } from "next/navigation";

export default function SeasonSwitcher({
  seasons,
  current,
}: {
  seasons: string[];
  current: string;
}) {
  const router = useRouter();

  return (
    <select
      className="season-select"
      value={current}
      onChange={(e) => router.push(`/temporadas/${encodeURIComponent(e.target.value)}`)}
    >
      {seasons.map((s) => (
        <option key={s} value={s}>
          Temporada {s}
        </option>
      ))}
    </select>
  );
}
