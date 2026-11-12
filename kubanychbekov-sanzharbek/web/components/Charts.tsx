"use client";

import { useI18n } from "./Providers";

export type Series = { key: string; label: string; color: string; values: number[] };

const W = 560;
const H = 230;
const PAD = { top: 16, right: 14, bottom: 30, left: 34 };

function niceMax(value: number): number {
  if (value <= 5) return 5;
  const step = 10 ** Math.floor(Math.log10(value));
  return Math.ceil(value / step) * step;
}

/** Line chart with a legend, axis labels, hover tooltips (SVG <title>) and a table fallback. */
export function LineChart({
  labels,
  series,
  title,
  description,
}: {
  labels: string[];
  series: Series[];
  title: string;
  description: string;
}) {
  const max = niceMax(Math.max(0, ...series.flatMap((s) => s.values)));
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (labels.length <= 1 ? 0 : (i / (labels.length - 1)) * innerW);
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(max * f));
  const everyN = Math.ceil(labels.length / 7);

  return (
    <figure style={{ margin: 0 }}>
      <svg
        className="chart"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={title}
        aria-describedby="line-chart-desc"
      >
        <desc id="line-chart-desc">{description}</desc>
        {ticks.map((tick) => (
          <g key={tick}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={y(tick)}
              y2={y(tick)}
              stroke="rgba(120,170,230,0.15)"
            />
            <text x={PAD.left - 8} y={y(tick) + 4} textAnchor="end">
              {tick}
            </text>
          </g>
        ))}
        {labels.map((label, i) =>
          i % everyN === 0 || i === labels.length - 1 ? (
            <text key={label} x={x(i)} y={H - 8} textAnchor="middle">
              {label}
            </text>
          ) : null,
        )}
        {series.map((s) => (
          <g key={s.key}>
            <polyline
              fill="none"
              stroke={s.color}
              strokeWidth="2.5"
              strokeLinejoin="round"
              points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ")}
            />
            {s.values.map((v, i) => (
              <circle key={`${s.key}-${labels[i]}`} cx={x(i)} cy={y(v)} r="4" fill={s.color}>
                <title>{`${labels[i]}: ${s.label} - ${v}`}</title>
              </circle>
            ))}
          </g>
        ))}
      </svg>
      <ul className="legend" style={{ marginTop: 6 }}>
        {series.map((s) => (
          <li key={s.key} style={{ ["--c" as string]: s.color }}>
            <i /> {s.label}
          </li>
        ))}
      </ul>
      <table className="sr-only">
        <caption>{title}</caption>
        <thead>
          <tr>
            <th />
            {series.map((s) => (
              <th key={s.key}>{s.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {labels.map((label, i) => (
            <tr key={label}>
              <th>{label}</th>
              {series.map((s) => (
                <td key={s.key}>{s.values[i]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

export type Slice = { label: string; value: number; color: string };

export function Donut({ slices, title }: { slices: Slice[]; title: string }) {
  const { t } = useI18n();
  const total = slices.reduce((sum, s) => sum + s.value, 0);
  const radius = 54;
  const circumference = 2 * Math.PI * radius;

  if (total === 0) return <p className="empty">{t("chart.noData")}</p>;

  // Each slice starts where the previous one ended (computed up front, no mutation in render).
  const arcs = slices
    .filter((s) => s.value > 0)
    .map((s, index, all) => ({
      ...s,
      length: (s.value / total) * circumference,
      start: all.slice(0, index).reduce((sum, p) => sum + (p.value / total) * circumference, 0),
    }));

  return (
    <div className="donut-row">
      <svg width="150" height="150" viewBox="0 0 150 150" role="img" aria-label={title}>
        <g transform="rotate(-90 75 75)">
          {arcs.map((s) => (
            <circle
              key={s.label}
              cx="75"
              cy="75"
              r={radius}
              fill="none"
              stroke={s.color}
              strokeWidth="18"
              strokeDasharray={`${s.length} ${circumference - s.length}`}
              strokeDashoffset={-s.start}
            >
              <title>{`${s.label}: ${s.value}`}</title>
            </circle>
          ))}
        </g>
        <text x="75" y="76" textAnchor="middle" fontSize="26" fontWeight="700" fill="#e6eef8">
          {total}
        </text>
        <text x="75" y="95" textAnchor="middle" fontSize="11" fill="#8fa6c4">
          {t("chart.total")}
        </text>
      </svg>
      <ul className="legend">
        {slices.map((s) => (
          <li key={s.label} style={{ ["--c" as string]: s.color }}>
            <i /> {s.label}
            <b>
              {s.value} ({Math.round((s.value / total) * 100)}%)
            </b>
          </li>
        ))}
      </ul>
    </div>
  );
}
