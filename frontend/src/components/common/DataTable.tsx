interface Column<T> {
  key: keyof T | string;
  header: string;
  render?: (row: T, index: number) => React.ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  emptyMessage?: string;
  rowTestId?: (row: T, index: number) => string;
  className?: string;
}

export default function DataTable<T extends object>({
  columns,
  data,
  emptyMessage = 'No data available.',
  rowTestId,
  className = '',
}: DataTableProps<T>) {
  return (
    <div className={`scrollbar-soft w-full overflow-x-auto rounded-xl ${className}`}>
      <table className="w-full min-w-[42rem] text-sm">
        <thead>
          <tr className="border-b border-[#e2eedd]">
            {columns.map((col) => (
              <th
                key={String(col.key)}
                className={`px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-[#5a7a52] ${col.className ?? ''}`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="text-center py-8 text-[#5a7a52] text-sm">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row, i) => (
              <tr
                key={i}
                className="border-b border-[#f0f7ed] transition-colors hover:bg-[#f8fdf6]"
                data-testid={rowTestId ? rowTestId(row, i) : undefined}
              >
                {columns.map((col) => (
                  <td key={String(col.key)} className={`safe-text px-3 py-2 text-[#1a2e14] ${col.className ?? ''}`}>
                    {col.render
                      ? col.render(row, i)
                      : String((row as Record<string, unknown>)[String(col.key)] ?? '')}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
