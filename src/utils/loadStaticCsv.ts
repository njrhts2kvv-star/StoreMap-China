export type CsvRecord = Record<string, string>;

/**
 * Minimal CSV loader for static assets placed under `public/data`.
 * For complex CSVs consider a dedicated parser.
 */
export async function loadStaticCsv(path: string): Promise<CsvRecord[]> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to load CSV: ${path}`);
  const text = (await res.text()).trim();
  if (!text) return [];
  const lines = text.split(/\r?\n/);
  const headers = lines[0].split(',');
  return lines
    .slice(1)
    .filter(Boolean)
    .map((line) => {
      const values = line.split(',');
      const record: CsvRecord = {};
      headers.forEach((key, idx) => {
        record[key] = values[idx]?.trim() ?? '';
      });
      return record;
    });
}

// Example usage:
// const djiStores = await loadStaticCsv('/data/dji_offline_stores.csv');
