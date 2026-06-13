import { FormEvent, KeyboardEvent, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Download, History, Search } from "lucide-react";

import { runUniversalQuery } from "../../api/uce";
import { useUCEStore } from "../../stores/uceStore";
import type { QueryResult, UCEModuleId } from "../../types/uce";

const MODULES: { id: UCEModuleId; label: string }[] = [
  { id: "crm", label: "CRM" },
  { id: "erp", label: "ERP" },
  { id: "hr", label: "HR" },
  { id: "inventory", label: "Inventory" },
  { id: "projects", label: "Projects" },
];

function detectType(input: string): "nl" | "sql" | "rest" {
  const value = input.trim().toLowerCase();
  if (value.startsWith("select") || value.startsWith("with ")) return "sql";
  if (value.startsWith("{") || value.includes("=") || value.startsWith("/")) return "rest";
  return "nl";
}

function exportFile(name: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

export default function QueryInterface() {
  const [input, setInput] = useState("projects delayed due to supply chain issues");
  const [selectedModules, setSelectedModules] = useState<UCEModuleId[]>([]);
  const [result, setResult] = useState<QueryResult | null>(null);
  const history = useUCEStore((state) => state.history);
  const addHistory = useUCEStore((state) => state.addHistory);
  const queryType = detectType(input);

  const mutation = useMutation({
    mutationFn: runUniversalQuery,
    onSuccess: (data) => {
      setResult(data);
      addHistory({ ...data, input, type: queryType, created_at: new Date().toISOString() });
    },
  });

  const columns = useMemo(() => {
    const keys = new Set<string>();
    result?.results.forEach((row) => Object.keys(row).forEach((key) => keys.add(key)));
    return Array.from(keys).slice(0, 12);
  }, [result]);

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (!input.trim()) return;
    mutation.mutate({
      input,
      type: queryType,
      modules: selectedModules.length ? selectedModules : undefined,
      limit: 50,
      offset: 0,
    });
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  const toggleModule = (module: UCEModuleId) => {
    setSelectedModules((current) => (current.includes(module) ? current.filter((item) => item !== module) : [...current, module]));
  };

  const exportJson = () => {
    exportFile("uce-query-results.json", JSON.stringify(result?.results ?? [], null, 2), "application/json");
  };

  const exportCsv = () => {
    const rows = result?.results ?? [];
    const csv = [columns.join(","), ...rows.map((row) => columns.map((column) => JSON.stringify(row[column] ?? "")).join(","))].join("\n");
    exportFile("uce-query-results.csv", csv, "text/csv");
  };

  return (
    <div className="space-y-6">
      <form onSubmit={submit} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-slate-950">Universal Query</h1>
            <p className="text-sm text-slate-500">Type detected: {queryType.toUpperCase()}</p>
          </div>
          <button className="inline-flex items-center gap-2 rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white" type="submit" disabled={mutation.isPending}>
            <Search className="h-4 w-4" />
            {mutation.isPending ? "Running" : "Run"}
          </button>
        </div>

        <textarea
          className="mt-4 min-h-32 w-full rounded-md border border-slate-300 p-3 text-sm outline-none focus:border-slate-950"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={onKeyDown}
        />

        <div className="mt-4 flex flex-wrap gap-2">
          {MODULES.map((module) => (
            <label key={module.id} className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm">
              <input type="checkbox" checked={selectedModules.includes(module.id)} onChange={() => toggleModule(module.id)} />
              {module.label}
            </label>
          ))}
        </div>
      </form>

      {mutation.error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">Query failed. Check your token and backend.</div> : null}

      {result ? (
        <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 p-4">
            <div className="text-sm text-slate-600">
              {result.total_count} results in {result.execution_ms}ms
              <span className="ml-2 text-slate-400">{result.modules_queried.join(", ")}</span>
            </div>
            <div className="flex gap-2">
              <button className="inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm" onClick={exportCsv} type="button">
                <Download className="h-4 w-4" />
                CSV
              </button>
              <button className="inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm" onClick={exportJson} type="button">
                <Download className="h-4 w-4" />
                JSON
              </button>
            </div>
          </div>
          <div className="overflow-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>{columns.map((column) => <th className="px-4 py-3 font-medium" key={column}>{column}</th>)}</tr>
              </thead>
              <tbody>
                {result.results.map((row, index) => (
                  <tr className="border-t border-slate-100" key={`${result.query_id}-${index}`}>
                    {columns.map((column) => (
                      <td className="max-w-80 px-4 py-3 align-top text-slate-700" key={column}>
                        {typeof row[column] === "object" ? JSON.stringify(row[column]) : String(row[column] ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
          <History className="h-4 w-4" />
          Query History
        </div>
        <div className="space-y-2">
          {history.map((item) => (
            <button key={item.query_id} className="block w-full rounded-md border border-slate-100 p-3 text-left text-sm hover:bg-slate-50" onClick={() => setInput(item.input)} type="button">
              <div className="font-medium text-slate-800">{item.input}</div>
              <div className="text-xs text-slate-500">{item.total_count} results · {item.execution_ms}ms · {item.modules_queried.join(", ")}</div>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

