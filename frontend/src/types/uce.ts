export type UCEModuleId = "crm" | "erp" | "hr" | "inventory" | "projects";

export interface QueryResult {
  query_id: string;
  results: Record<string, unknown>[];
  modules_queried: string[];
  execution_ms: number;
  total_count: number;
  ai_explanation?: string | null;
}

export interface QueryHistoryItem extends QueryResult {
  input: string;
  type: "nl" | "sql" | "rest";
  created_at: string;
}

export interface UCEEvent {
  id: string;
  event_type: string;
  source_module: string;
  entity_type: string;
  entity_id: string;
  payload: Record<string, unknown>;
  created_at: string;
}

