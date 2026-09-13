"use client";
import { useRouter } from "next/navigation";

export default function SeasonPicker({ seasons, current }: { seasons: string[]; current: string }) {
  const router = useRouter();
  return (
    <select
      className="season-select"
      value={current}
      onChange={(e) => router.push(`/evolucion?season=${encodeURIComponent(e.target.value)}`)}
    >
      {seasons.map((s) => (
        <option key={s} value={s}>Temporada {s}</option>
      ))}
    </select>
  );
}