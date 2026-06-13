import { api } from "./client.js";
import type { QueryResult, UCEModuleId } from "../types/uce";

export interface UniversalQueryPayload {
  input: string;
  type: "nl" | "sql" | "rest" | "natural_language";
  modules?: UCEModuleId[];
  limit?: number;
  offset?: number;
}

export async function runUniversalQuery(payload: UniversalQueryPayload): Promise<QueryResult> {
  const { data } = await api.post("/v1/query/", payload);
  return data.data as QueryResult;
}

export async function getModuleRegistry() {
  const { data } = await api.get("/v1/modules/");
  return data.data?.results ?? data.data ?? [];
}

