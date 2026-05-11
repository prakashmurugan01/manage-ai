import { Link } from "react-router-dom";

import Button from "../components/ui/Button.jsx";

export default function NotFound() {
  return (
    <main className="grid min-h-screen place-items-center bg-ink-950 px-4">
      <div className="panel max-w-md p-6 text-center">
        <h1 className="text-2xl font-semibold text-white">Page not found</h1>
        <p className="mt-2 text-sm text-slate-400">The requested workspace route does not exist.</p>
        <Link to="/dashboard" className="mt-5 inline-flex">
          <Button>Dashboard</Button>
        </Link>
      </div>
    </main>
  );
}
