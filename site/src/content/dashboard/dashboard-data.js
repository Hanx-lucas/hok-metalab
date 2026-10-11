export function chronologicalRows(rows) {
  return [...rows].sort((left, right) => String(left.week).localeCompare(String(right.week)));
}

// Sessions are additive across the reviewed product/region slices.
export function aggregateSessions(rows, dimensions) {
  const cells = new Map();
  for (const row of rows) {
    const key = JSON.stringify(dimensions.map((field) => row[field]));
    const cell = cells.get(key) ?? Object.fromEntries(dimensions.map((field) => [field, row[field]]));
    cell.sessions = (cell.sessions ?? 0) + (Number(row.sessions) || 0);
    cells.set(key, cell);
  }
  return [...cells.values()];
}

export function progressPercent(attainment) {
  return Math.min(100, Math.max(0, (attainment ?? 0) / 1.25 * 100));
}

export function regionalTotals(rows, locations) {
  const regions = new Map();
  for (const row of rows) {
    const region = String(row.region ?? "Unknown region");
    const total = regions.get(region) ?? { region, accounts: 0, activeUsers: 0, elevated: 0,
      color: "var(--secondary)", ...locations[region] };
    total.accounts += 1;
    total.activeUsers += Number(row.activeUsers) || 0;
    total.elevated += Number(row.riskTier === "Elevated");
    regions.set(region, total);
  }
  return [...regions.values()];
}
