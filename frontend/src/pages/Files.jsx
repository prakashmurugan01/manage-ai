import { useEffect, useState } from "react";

import { listFrom } from "../api/client.js";
import { documentsApi, projectsApi } from "../api/services.js";
import FileTable from "../components/files/FileTable.jsx";
import FileUploader from "../components/files/FileUploader.jsx";
import Page from "../components/ui/Page.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { canManage, ROLES } from "../utils/rbac.js";

export default function Files() {
  const { user } = useAuth();
  const [files, setFiles] = useState([]);
  const [projects, setProjects] = useState([]);

  useEffect(() => {
    documentsApi.list().then((response) => setFiles(listFrom(response)));
    projectsApi.list().then((response) => setProjects(listFrom(response)));
  }, []);

  async function remove(id) {
    await documentsApi.remove(id);
    setFiles((items) => items.filter((item) => item.id !== id));
  }

  async function review(id, payload) {
    const { data } = await documentsApi.review(id, payload);
    setFiles((items) => items.map((item) => (item.id === id ? data : item)));
  }

  return (
    <Page title="Project Files" subtitle="Developer submissions, project documents, admin review, approvals, corrections, and direct previews.">
      {(canManage(user) || user?.role === ROLES.DEVELOPER) && (
        <FileUploader projects={projects} defaultVisibility="INTERNAL" onUploaded={(file) => setFiles((items) => [file, ...items])} />
      )}
      <div className="mt-6">
        <FileTable files={files} onDelete={canManage(user) ? remove : null} onReview={canManage(user) ? review : null} />
      </div>
    </Page>
  );
}
