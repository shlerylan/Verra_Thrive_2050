import React, { useState } from "react";
import type { LeakagePreview } from "./api";
import { LeakageScenario } from "./LeakageScenario";

const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const fmt = (value: number) => number.format(value);

const productionSeries = [
  { key: "baseline_project_production", area: "Project area", color: "#295f9d", baseline: true },
  { key: "monitored_project_production", area: "Project area", color: "#295f9d", baseline: false },
  { key: "baseline_mitigation_production", area: "Leakage mitigation area", color: "#23734d", baseline: true },
  { key: "monitored_mitigation_production", area: "Leakage mitigation area", color: "#23734d", baseline: false },
] as const;

function ProductionChart({ years, unit, selectedYear }: {
  years: LeakagePreview["annual_results"]; unit: string; selectedYear: number;
}) {
  const peak = Math.max(1, ...years.flatMap((row) => productionSeries.map(({ key }) => row[key])));
  const magnitude = 10 ** Math.floor(Math.log10(peak));
  const top = Math.ceil(peak / magnitude) * magnitude;
  const x = (i: number) => years.length === 1 ? 236 : 68 + i * 336 / (years.length - 1);
  const y = (value: number) => 368 - value / top * 320;
  return <figure className="production-chart">
    <figcaption className="production-legend">
      <span><i style={{ borderColor: productionSeries[0].color }} /> Project area</span>
      <span><i style={{ borderColor: productionSeries[2].color }} /> Leakage mitigation area</span>
      <span><i className="expected" /> Baseline (expected)</span>
      <span><i /> Monitored count</span>
    </figcaption>
    <svg viewBox="0 0 432 432" role="img" aria-label={`Project and mitigation area production by year, in ${unit}`}>
      {[0, top / 4, top / 2, 3 * top / 4, top].map((tick) => <g key={tick}>
        <text x="59" y={y(tick) + 4} textAnchor="end">{fmt(tick)}</text>
        <line x1="68" x2="404" y1={y(tick)} y2={y(tick)} stroke="#dce3dc" />
      </g>)}
      {years.map((point, i) => <g key={point.year}>
        {point.year === selectedYear && <line x1={x(i)} x2={x(i)} y1={y(top)} y2={y(0)} stroke="#aabbb0" strokeDasharray="3 4" />}
        <text x={x(i)} y="392" textAnchor="middle">{point.year}</text>
      </g>)}
      <text x="68" y="26">Production ({unit})</text>
      {productionSeries.map(({ key, area, color, baseline }) => <g key={key}>
        <polyline points={years.map((point, i) => `${x(i)},${y(point[key])}`).join(" ")}
          fill="none" stroke={color} strokeWidth="2.5" strokeDasharray={baseline ? "6 4" : undefined} />
        {years.map((point, i) => <circle key={point.year} cx={x(i)} cy={y(point[key])} r="4"
          fill={baseline ? "white" : color} stroke={color} strokeWidth="2">
          <title>{point.year} · {area} · {baseline ? "Baseline" : "Monitored count"}: {fmt(point[key])} {unit}</title>
        </circle>)}
      </g>)}
    </svg>
  </figure>;
}

type AreaDensity = { name: string; color: string; area: number | null; density: number | null; monitored: number };

function AreaDensityChart({ areas, unit, year }: { areas: AreaDensity[]; unit: string; year: number }) {
  const measured = areas.flatMap((entry) =>
    entry.area && entry.area > 0 && entry.density !== null ? [{ ...entry, hectares: entry.area, density: entry.density }] : [],
  );
  if (measured.length === 0) {
    return <p>Enter both land areas in the Excel template to compare production density.</p>;
  }

  const totalArea = measured.reduce((sum, entry) => sum + entry.hectares, 0);
  const maxDensity = Math.max(...measured.map((entry) => entry.density)) || 1;
  const origin = 70;
  const width = 505;
  const bottom = 171;
  const height = 130;

  return (
    <figure className="production-chart density-chart">
      <figcaption>
        <strong>{year} · Land area and monitored density</strong>
        <p>Width shows land area. Height shows monitored production per hectare. Rectangle area represents total monitored production.</p>
      </figcaption>
      <svg viewBox="0 0 610 223" role="img"
        aria-label={measured.map((entry) =>
          `${entry.name}: ${fmt(entry.hectares)} hectares, ${fmt(entry.density)} ${unit} per hectare`).join("; ")}>
        <text x={origin} y="18">Monitored density ({unit}/ha)</text>
        {[0, maxDensity / 2, maxDensity].map((tick, i) => {
          const y = bottom - i * height / 2;
          return <g key={i}>
            <text x={origin - 9} y={y + 4} textAnchor="end">{fmt(tick)}</text>
            <line x1={origin} x2={origin + width} y1={y} y2={y} stroke="#dce3dc" />
          </g>;
        })}
        {measured.map((entry, i) => {
          const offset = measured.slice(0, i).reduce((sum, previous) => sum + previous.hectares, 0);
          const left = origin + width * offset / totalArea;
          const span = width * entry.hectares / totalArea;
          const rise = height * entry.density / maxDensity;
          return <g key={entry.name}>
            <title>{entry.name}: {fmt(entry.hectares)} ha · {fmt(entry.density)} {unit}/ha · {fmt(entry.monitored)} {unit}</title>
            <rect x={left} y={bottom - rise} width={span} height={rise} fill={entry.color} fillOpacity="0.7" />
            <line x1={left} x2={left + span} y1={bottom + 5} y2={bottom + 5} stroke={entry.color} strokeWidth="4" />
            {rise === 0 && <line x1={left} x2={left + span} y1={bottom} y2={bottom} stroke={entry.color} strokeDasharray="3 3" />}
          </g>;
        })}
        <text x={origin} y="198">0</text>
        <text x={origin + width} y="198" textAnchor="end">{fmt(totalArea)} ha</text>
        <text x={origin + width / 2} y="218" textAnchor="middle">Combined land area shown</text>
      </svg>
      {measured.length < areas.length && <p>Area was supplied for one zone. Add the other area in Excel to compare both zones.</p>}
    </figure>
  );
}

export function LeakageCharts({ projectId, preview }: { projectId: string; preview: LeakagePreview }) {
  const [index, setIndex] = useState(0);
  const { annual_results: years, production_unit: unit } = preview;
  const row = years[index];
  if (!row) return null;
  const areas = [
    { name: "Project area", color: productionSeries[0].color, area: preview.project_area_ha, density: row.monitored_project_density, baselineDensity: row.baseline_project_density, monitored: row.monitored_project_production, baseline: row.baseline_project_production },
    { name: "Leakage mitigation area", color: productionSeries[2].color, area: preview.mitigation_area_ha, density: row.monitored_mitigation_density, baselineDensity: row.baseline_mitigation_density, monitored: row.monitored_mitigation_production, baseline: row.baseline_mitigation_production },
  ];

  return <div className="reference-scenario">
    {preview.reference_replay && <p className="reference-caution"><strong>Brazil Cerrado 1 workbook replay.</strong> Areas come from VCS5511_ARR!C4 and C7. Historical labels include the project start year. Repeated monitoring entries are workbook values.</p>}
    <h3>Annual production ({unit})</h3>
    <p>Monitored counts come from the workbook. Test and scenario workbooks can contain assumed values.</p>
    <div className="production-comparison">
      <ProductionChart years={years} unit={unit} selectedYear={row.year} />
      <section className="production-conclusion" aria-labelledby="coverage-title">
        <label htmlFor="visual-year">Monitoring year</label>
        <select id="visual-year" value={index} onChange={(event) => { setIndex(Number(event.target.value)); }}>
          {years.map((item, i) => <option key={item.year} value={i}>{item.year}</option>)}
        </select>
        <div aria-live="polite">
          <h4 id="coverage-title">{row.foregone_production <= 0 ? "No project-area shortfall"
            : row.production_subject_to_leakage === 0 ? "Mitigation covers the shortfall" : "Mitigation leaves a shortfall"}</h4>
          <dl className="reference-inputs">
            <div><dt>Project area below baseline</dt><dd>{fmt(row.project_shortfall)} {unit}</dd></div>
            <div><dt>Mitigation area vs. its baseline</dt><dd>{fmt(row.leakage_mitigation)} {unit}</dd></div>
            <div><dt>Remaining production subject to leakage</dt><dd>{fmt(row.production_subject_to_leakage)} {unit}</dd></div>
            <div><dt>Estimated leakage emissions</dt><dd>{fmt(row.leakage_t_co2e)} t CO₂e</dd></div>
          </dl>
          <p>Only the mitigation area's change from its own baseline goes into the comparison. The model converts the remaining production to new land area, then estimates emissions.</p>
        </div>
      </section>
    </div>
    <details><summary>Historical production</summary>
      <div className="cattle-table"><table>
        <thead><tr><th>Year</th><th>Project ({unit})</th><th>Mitigation ({unit})</th></tr></thead>
        <tbody>{preview.historical_production.map((item) => <tr key={item.year}><th scope="row">{item.year}</th><td>{fmt(item.project)}</td><td>{fmt(item.mitigation)}</td></tr>)}</tbody>
      </table></div>
    </details>
    <AreaDensityChart areas={areas} unit={unit} year={row.year} />
    <div className="reference-columns">
      {areas.map((area) => <section key={area.name}>
        <h4 style={{ color: area.color }}>{area.name}</h4>
        <dl className="reference-inputs">
          <div><dt>Area</dt><dd>{area.area ? fmt(area.area) + " ha" : "Not supplied"}</dd></div>
          <div><dt>Expected without project</dt><dd>{fmt(area.baseline)} {unit}</dd></div>
          <div><dt>Monitored count</dt><dd>{fmt(area.monitored)} {unit}</dd></div>
          <div><dt>Expected density</dt><dd>{area.baselineDensity !== null ? fmt(area.baselineDensity) + " " + unit + "/ha" : "Unavailable"}</dd></div>
          <div><dt>Monitored density</dt><dd>{area.density !== null ? fmt(area.density) + " " + unit + "/ha" : "Unavailable"}</dd></div>
        </dl>
      </section>)}
    </div>
    <LeakageScenario key={`${projectId}:${preview.source_workbook_id}:${preview.source_sha256}:${row.year}`}
      projectId={projectId} workbookId={preview.source_workbook_id}
      sourceSha256={preview.source_sha256} row={row} unit={unit} />
  </div>;
}
