import { api } from "./client.js";

export function fetchNetlifyStatus() {
  return api.get("/netlify-status/").then((res) => res.data);
}

export function redeployNetlify(siteId) {
  return api.post("/netlify/redeploy/", siteId ? { site_id: siteId } : {}).then((res) => res.data);
}
