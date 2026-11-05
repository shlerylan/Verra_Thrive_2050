import React from "react";

export function LeakageGuide() {
  return <div className="template-guide">
    <p><strong>Start with Info.</strong> Edit the yellow cells in the blank template.</p>
    <details>
      <summary>How to fill the Leakage template</summary>
      <ol>
        <li><strong>Data:</strong> enter historical and monitoring totals for both areas, plus expected yield on any new land.</li>
        <li><strong>Parameters:</strong> enter the start year, growth and land-carbon inputs. Parameters!B8 is biomass carbon loss. Enter both areas in hectares for the density charts.</li>
      </ol>
      <p>Upload the Brazil Cerrado 1 sample unchanged to replay the workbook. The synthetic example covers 2023–2027 and gives 789.25 t CO2e for 2023.</p>
    </details>
  </div>;
}
